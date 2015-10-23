import time
from ethereum.config import Env
from ethereum.utils import sha3
import rlp
from rlp.utils import encode_hex
from ethereum import processblock
from ethereum.slogging import get_logger
from ethereum.chain import Chain
from ethereum.refcount_db import RefcountDB
from ethereum.blocks import Block, VerificationFailed
from ethereum.transactions import Transaction
from devp2p.service import WiredService
from ethereum import config as ethereum_config
import gevent
import gevent.lock
from collections import deque
from gevent.queue import Queue
from pyethapp.eth_service import ChainService as eth_ChainService
from .consensus.protocol import HDCProtocol, HDCProtocolError
from .consensus.base import Signed, VotingInstruction, BlockProposal
from .consensus.base import VoteBlock, VoteNil, HDCBlockHeader, LockSet
from .consensus.utils import phx
from .consensus.manager import ConsensusManager
from .consensus.contract import ConsensusContract


log = get_logger('hdc.chainservice')


# patch to get context switches between tx replay
processblock_apply_transaction = processblock.apply_transaction


def apply_transaction(block, tx):
    # import traceback
    # print traceback.print_stack()
    log.debug('apply_transaction ctx switch', tx=tx.hash.encode('hex')[:8])
    gevent.sleep(0.001)
    return processblock_apply_transaction(block, tx)
processblock.apply_transaction = apply_transaction


rlp_hash_hex = lambda data: encode_hex(sha3(rlp.encode(data)))


class DuplicatesFilter(object):

    def __init__(self, max_items=1024):
        self.max_items = max_items
        self.filter = list()

    def update(self, data):
        "returns True if unknown"
        if data not in self.filter:
            self.filter.append(data)
            if len(self.filter) > self.max_items:
                self.filter.pop(0)
            return True
        else:
            self.filter.append(self.filter.pop(0))
            return False

    def __contains__(self, v):
        return v in self.filter


def update_watcher(chainservice):
    timeout = 180
    d = dict(head=chainservice.chain.head)

    def up(b):
        log.debug('watcher head updated')
        d['head'] = b
    chainservice.on_new_head_cbs.append(lambda b: up(b))

    while True:
        last = d['head']
        gevent.sleep(timeout)
        assert last != d['head'], 'no updates for %d secs' % timeout


class ChainService(eth_ChainService):

    """
    Manages the chain and requests to it.
    """
    # required by BaseService
    name = 'chain'
    default_config = dict(eth=dict(network_id=0,
                                   genesis='',
                                   pruning=-1,
                                   block=ethereum_config.default_config),
                          hdc=dict(validators=[]),
                          )

    # required by WiredService
    wire_protocol = HDCProtocol  # create for each peer

    # initialized after configure:
    chain = None
    genesis = None
    synchronizer = None
    config = None
    block_queue_size = 1024
    transaction_queue_size = 1024
    processed_gas = 0
    processed_elapsed = 0

    def __init__(self, app):
        self.config = app.config
        sce = self.config['eth']
        if int(sce['pruning']) >= 0:
            self.db = RefcountDB(app.services.db)
            if "I am not pruning" in self.db.db:
                raise Exception("This database was initialized as non-pruning."
                                " Kinda hard to start pruning now.")
            self.db.ttl = int(sce['pruning'])
            self.db.db.put("I am pruning", "1")
        else:
            self.db = app.services.db
            if "I am pruning" in self.db:
                raise Exception("This database was initialized as pruning."
                                " Kinda hard to stop pruning now.")
            self.db.put("I am not pruning", "1")

        if 'network_id' in self.db:
            db_network_id = self.db.get('network_id')
            if db_network_id != str(sce['network_id']):
                raise Exception("This database was initialized with network_id {} "
                                "and can not be used when connecting to network_id {}".format(
                                    db_network_id, sce['network_id'])
                                )

        else:
            self.db.put('network_id', str(sce['network_id']))
            self.db.commit()

        assert self.db is not None

        WiredService.__init__(self, app)
        log.info('initializing chain')
        coinbase = app.services.accounts.coinbase
        env = Env(self.db, sce['block'])
        self.chain = Chain(env, new_head_cb=self._on_new_head, coinbase=coinbase)

        log.info('chain at', number=self.chain.head.number)
        if 'genesis_hash' in sce:
            assert sce['genesis_hash'] == self.chain.genesis.hex_hash()

        self.transaction_queue = Queue(maxsize=self.transaction_queue_size)
        self.add_blocks_lock = False
        self.add_transaction_lock = gevent.lock.Semaphore()
        self.broadcast_filter = DuplicatesFilter()
        self.on_new_head_cbs = []
        self.on_new_head_candidate_cbs = []
        self.newblock_processing_times = deque(maxlen=1000)

        # Consensus
        self.consensus_contract = ConsensusContract(validators=self.config['hdc']['validators'])
        self.consensus_manager = ConsensusManager(self, self.consensus_contract,
                                                  self.consensus_privkey)

    def start(self):
        super(ChainService, self).start()
        self.consensus_manager.process()

    # interface accessed by ConensusManager

    def log(self, msg, *args, **kargs):
        log.debug(msg, *args, **kargs)

    @property
    def consensus_privkey(self):
        return self.app.services.accounts[0].privkey

    def sign(self, obj):
        assert isinstance(obj, Signed)
        obj.sign(self.consensus_privkey)

    @property
    def now(self):
        return time.time()

    def setup_alarm(self, delay, cb, *args):
        log.debug('setting up alarm')

        def _trigger():
            gevent.sleep(delay)
            log.debug('alarm triggered')
            cb(*args)
        gevent.spawn(_trigger)

    def commit_block(self, blk):
        assert isinstance(blk.header, HDCBlockHeader)
        self.add_transaction_lock.acquire()
        success = self.chain.add_block(blk,  forward_pending_transactions=True)
        self.add_transaction_lock.release()
        log.info('new head', head=self.chain.head)
        return success

    def link_block(self, t_block):
        assert isinstance(t_block.header, HDCBlockHeader)
        self.add_transaction_lock.acquire()
        block = self._link_block(t_block)
        if not block:
            return
        assert block.get_parent() == self.chain.head, (block.get_parent(), self.chain.head)
        assert block.header.coinbase == t_block.header.coinbase
        self.add_transaction_lock.release()
        return block

    def _link_block(self, t_block):
        assert isinstance(t_block.header, HDCBlockHeader)
        if t_block.header.hash in self.chain:
            log.warn('known block', block=t_block)
            return
        if t_block.header.prevhash not in self.chain:
            log.warn('missing parent', block=t_block, head=self.chain.head,
                     prevhash=phx(t_block.header.prevhash))
            return
        if isinstance(t_block, Block):
            return True  # already deserialized
        try:  # deserialize
            st = time.time()
            block = t_block.to_block(env=self.chain.env)
            elapsed = time.time() - st
            log.debug('deserialized', elapsed='%.4fs' % elapsed, ts=time.time(),
                      gas_used=block.gas_used, gpsec=self.gpsec(block.gas_used, elapsed))
            assert block.header.check_pow()
        except processblock.InvalidTransaction as e:
            log.warn('invalid transaction', block=t_block, error=e, FIXME='ban node')
            return
        except VerificationFailed as e:
            log.warn('verification failed', error=e, FIXME='ban node')
            return
        return block

    ###############################################################################

    @property
    def is_syncing(self):
        return self.consensus_manager.synchronizer.is_syncing

    @property
    def is_mining(self):
        return self.chain.coinbase in self.config['hdc']['validators']

    # wire protocol receivers ###########

    # transactions

    def on_receive_transactions(self, proto, transactions):
        "receives rlp.decoded serialized"
        log.debug('----------------------------------')
        log.debug('remote_transactions_received', count=len(transactions), remote_id=proto)
        for tx in transactions:
            self.add_transaction(tx, origin=proto)

    # blocks / proposals ################

    def on_receive_getblockproposals(self, proto, blocknumbers):
        log.debug('----------------------------------')
        log.debug("on_receive_getblockproposals", count=len(blocknumbers))
        found = []
        for i, height in enumerate(blocknumbers):
            if i == self.wire_protocol.max_getproposals_count:
                break
            assert isinstance(height, int)  # integers
            assert i == 0 or height > blocknumbers[i - 1]   # sorted
            if height > self.chain.head.number:
                log.debug("unknown block requested", height=height)
                break
            rlp_data = self.consensus_manager.get_blockproposal_rlp_by_height(height)
            assert isinstance(rlp_data, bytes)
            found.append(rlp_data)
        if found:
            log.debug("found", count=len(found))
            proto.send_blockproposals(*found)

    def on_receive_blockproposals(self, proto, proposals):
        log.debug('----------------------------------')
        self.consensus_manager.log('received proposals', sender=proto)
        log.debug("recv proposals", num=len(proposals), remote_id=proto)
        self.consensus_manager.synchronizer.receive_blockproposals(proposals)

    def on_receive_newblockproposal(self, proto, proposal):
        if proposal.hash in self.broadcast_filter:
            return
        log.debug('----------------------------------')
        self.consensus_manager.log('receive proposal', sender=proto)
        log.debug("recv newblockproposal", proposal=proposal, remote_id=proto)
        # self.synchronizer.receive_newproposal(proto, proposal)
        assert isinstance(proposal, BlockProposal)
        assert isinstance(proposal.block.header, HDCBlockHeader)
        isvalid = self.consensus_manager.add_proposal(proposal, proto)
        if isvalid:
            self.broadcast(proposal, origin_proto=proto)
        self.consensus_manager.process()

    def on_receive_votinginstruction(self, proto, votinginstruction):
        if votinginstruction.hash in self.broadcast_filter:
            return
        log.debug('----------------------------------')
        log.debug("recv votinginstruction", proposal=votinginstruction, remote_id=proto)
        # self.synchronizer.receive_newproposal(proto, proposal)
        isvalid = self.consensus_manager.add_proposal(votinginstruction, proto)
        if isvalid:
            self.broadcast(votinginstruction, origin_proto=proto)

        self.consensus_manager.process()

    #  votes

    def on_receive_vote(self, proto, vote):
        if vote.hash in self.broadcast_filter:
            return
        log.debug('----------------------------------')
        log.debug("recv vote", vote=vote, remote_id=proto)
        isvalid = self.consensus_manager.add_vote(vote, proto)
        if isvalid:
            self.broadcast(vote, origin_proto=proto)
        self.consensus_manager.process()

    #  start

    def on_receive_status(self, proto, eth_version, network_id, genesis_hash, current_lockset):
        log.debug('----------------------------------')
        log.debug('status received', proto=proto, eth_version=eth_version)
        assert eth_version == proto.version, (eth_version, proto.version)
        if network_id != self.config['eth'].get('network_id', proto.network_id):
            log.warn("invalid network id", remote_network_id=network_id,
                     expected_network_id=self.config['eth'].get('network_id', proto.network_id))
            raise HDCProtocolError('wrong network_id')

        # check genesis
        if genesis_hash != self.chain.genesis.hash:
            log.warn("invalid genesis hash", remote_id=proto, genesis=genesis_hash.encode('hex'))
            raise HDCProtocolError('wrong genesis block')

        assert isinstance(current_lockset, LockSet)
        if len(current_lockset):
            log.debug('adding received lockset', ls=current_lockset)
            for v in current_lockset.votes:
                self.consensus_manager.add_vote(v, proto)

        self.consensus_manager.process()

        # send last BlockProposal
        p = self.consensus_manager.last_blockproposal
        if p:
            self.consensus_manager.log('sending proposal', p=p)
            proto.send_newblockproposal(p)

        # send transactions
        transactions = self.chain.get_transactions()
        if transactions:
            log.debug("sending transactions", remote_id=proto)
            proto.send_transactions(*transactions)

    def on_wire_protocol_start(self, proto):
        log.debug('----------------------------------')
        log.debug('on_wire_protocol_start', proto=proto)
        assert isinstance(proto, self.wire_protocol)
        # register callbacks
        proto.receive_status_callbacks.append(self.on_receive_status)
        proto.receive_transactions_callbacks.append(self.on_receive_transactions)
        proto.receive_blockproposals_callbacks.append(self.on_receive_blockproposals)
        proto.receive_getblockproposals_callbacks.append(self.on_receive_getblockproposals)
        proto.receive_newblockproposal_callbacks.append(self.on_receive_newblockproposal)
        proto.receive_votinginstruction_callbacks.append(self.on_receive_votinginstruction)
        proto.receive_vote_callbacks.append(self.on_receive_vote)

        # send status
        proto.send_status(genesis_hash=self.chain.genesis.hash,
                          current_lockset=self.consensus_manager.active_round.lockset)

    def on_wire_protocol_stop(self, proto):
        assert isinstance(proto, self.wire_protocol)
        log.debug('----------------------------------')
        log.debug('on_wire_protocol_stop', proto=proto)

    def broadcast(self, obj, origin_proto=None):
        """
        """
        fmap = {BlockProposal: 'newblockproposal', VoteBlock: 'vote', VoteNil: 'vote',
                VotingInstruction: 'votinginstruction', Transaction: 'transaction'}
        if not self.broadcast_filter.update(obj.hash):
            log.debug('already broadcasted', obj=obj)
            return
        if isinstance(obj, BlockProposal):
            assert obj.sender == obj.block.header.coinbase
        log.debug('broadcasting', obj=obj)
        bcast = self.app.services.peermanager.broadcast
        bcast(HDCProtocol, fmap[type(obj)], args=(obj,),
              exclude_peers=[origin_proto.peer] if origin_proto else [])

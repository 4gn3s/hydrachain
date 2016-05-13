from ethereum import slogging
from ethereum.exceptions import UnsignedTransaction, InvalidTransaction, InsufficientStartGas
from ethereum.processblock import validate_transaction, CREATE_CONTRACT_ADDRESS, create_contract, apply_msg, \
    lazy_safe_encode, VMExt

# from hydrachain.contracts.contract_utils import ContractUtils
from ethereum.tester import vm
import sys
import rlp
from rlp.sedes import CountableList, binary
from rlp.utils import decode_hex, encode_hex, ascii_chr
from ethereum import opcodes
from ethereum import utils
from ethereum import specials
from ethereum import bloom
from ethereum import vm as vm
from ethereum.exceptions import InvalidNonce, InsufficientStartGas, UnsignedTransaction, \
        BlockGasLimitReached, InsufficientBalance
from ethereum.utils import safe_ord, mk_contract_address
from ethereum import transactions
import ethereum.config as config

sys.setrecursionlimit(100000)

from ethereum.slogging import get_logger
log_tx = get_logger('eth.pb.tx')
log_msg = get_logger('eth.pb.msg')
log_state = get_logger('eth.pb.msg.state')

TT255 = 2 ** 255
TT256 = 2 ** 256
TT256M1 = 2 ** 256 - 1

OUT_OF_GAS = -1

# contract creating transactions send to an empty address
CREATE_CONTRACT_ADDRESS = b''

log = slogging.get_logger('app')


class UnauthorizedTransaction(InvalidTransaction):
    pass


class ProcessblockWrapper:
    @staticmethod
    def validate_transaction_wrapper(block, tx):
        if not tx.sender:  # sender is set and validated on Transaction initialization
            raise UnsignedTransaction(tx)

        # log.info(block.config)
        contract_address = block.config['hdc']["user_registry_contract_address"]

        if contract_address:
            print("validating tx AUTH AUTH ATUH")
            # log.info("validating if transaction sender is authorized")
            # contract_utils = ContractUtils(block.config['jsonrpc']['listen_port'])
            # contract_utils.new_contract(contract_address)
            # if not contract_utils.contract.isAuthorizedToTransact(tx.sender, block.number):
            #     raise UnauthorizedTransaction(tx)

        return validate_transaction(block, tx)

    @staticmethod
    def apply_transaction(block, tx):
        validate_transaction(block, tx)

        # print block.get_nonce(tx.sender), '@@@'

        def rp(what, actual, target):
            return '%r: %r actual:%r target:%r' % (tx, what, actual, target)

        intrinsic_gas = tx.intrinsic_gas_used
        if block.number >= block.config['HOMESTEAD_FORK_BLKNUM']:
            assert tx.s * 2 < transactions.secpk1n
            if not tx.to or tx.to == CREATE_CONTRACT_ADDRESS:
                intrinsic_gas += opcodes.CREATE[3]
                if tx.startgas < intrinsic_gas:
                    raise InsufficientStartGas(rp('startgas', tx.startgas, intrinsic_gas))

        log_tx.debug('TX NEW', tx_dict=tx.log_dict())
        # start transacting #################
        block.increment_nonce(tx.sender)

        # buy startgas
        assert block.get_balance(tx.sender) >= tx.startgas * tx.gasprice
        block.delta_balance(tx.sender, -tx.startgas * tx.gasprice)
        message_gas = tx.startgas - intrinsic_gas
        message_data = vm.CallData([safe_ord(x) for x in tx.data], 0, len(tx.data))
        message = vm.Message(tx.sender, tx.to, tx.value, message_gas, message_data, code_address=tx.to)


        log_tx.debug(message.code_address in specials.specials)
        log_tx.debug(opcodes.GIDENTITYBASE + opcodes.GIDENTITYWORD * (utils.ceil32(message.data.size) // 32))

        # MESSAGE
        ext = VMExt(block, tx)
        if tx.to and tx.to != CREATE_CONTRACT_ADDRESS:
            result, gas_remained, data = apply_msg(ext, message)
            log_tx.debug('_res_', result=result, gas_remained=gas_remained, data=lazy_safe_encode(data))
        else:  # CREATE
            result, gas_remained, data = create_contract(ext, message)
            assert utils.is_numeric(gas_remained)
            log_tx.debug('_create_', result=result, gas_remained=gas_remained, data=lazy_safe_encode(data))

        assert gas_remained >= 0

        log_tx.debug("TX APPLIED", result=result, gas_remained=gas_remained,
                     data=lazy_safe_encode(data))

        if not result:  # 0 = OOG failure in both cases
            log_tx.debug('TX FAILED', reason='out of gas',
                         startgas=tx.startgas, gas_remained=gas_remained)
            block.gas_used += tx.startgas
            block.delta_balance(block.coinbase, tx.gasprice * tx.startgas)
            output = b''
            success = 0
        else:
            log_tx.debug('TX SUCCESS', data=lazy_safe_encode(data))
            gas_used = tx.startgas - gas_remained
            block.refunds += len(set(block.suicides)) * opcodes.GSUICIDEREFUND
            if block.refunds > 0:
                log_tx.debug('Refunding', gas_refunded=min(block.refunds, gas_used // 2))
                gas_remained += min(block.refunds, gas_used // 2)
                gas_used -= min(block.refunds, gas_used // 2)
                block.refunds = 0
            # sell remaining gas
            block.delta_balance(tx.sender, tx.gasprice * gas_remained)
            block.delta_balance(block.coinbase, tx.gasprice * gas_used)
            block.gas_used += gas_used
            if tx.to:
                output = b''.join(map(ascii_chr, data))
            else:
                output = data
            success = 1
        block.commit_state()
        suicides = block.suicides
        block.suicides = []
        for s in suicides:
            block.ether_delta -= block.get_balance(s)
            block.set_balance(s, 0)
            block.del_account(s)
        block.add_transaction_to_list(tx)
        block.logs = []
        return success, output

    @staticmethod
    def _apply_msg(ext, msg, code):
        trace_msg = log_msg.is_active('trace')
        if trace_msg:
            log_msg.debug("MSG APPLY", sender=encode_hex(msg.sender), to=encode_hex(msg.to),
                          gas=msg.gas, value=msg.value,
                          data=encode_hex(msg.data.extract_all()))
            if log_state.is_active('trace'):
                log_state.trace('MSG PRE STATE SENDER', account=msg.sender.encode('hex'),
                                bal=ext.get_balance(msg.sender),
                                state=ext.log_storage(msg.sender))
                log_state.trace('MSG PRE STATE RECIPIENT', account=msg.to.encode('hex'),
                                bal=ext.get_balance(msg.to),
                                state=ext.log_storage(msg.to))
            # log_state.trace('CODE', code=code)
        # Transfer value, instaquit if not enough
        snapshot = ext._block.snapshot()
        if msg.transfers_value:
            if not ext._block.transfer_value(msg.sender, msg.to, msg.value):
                log_msg.debug('MSG TRANSFER FAILED', have=ext.get_balance(msg.to),
                              want=msg.value)
                return 1, msg.gas, []
        # Main loop
        if msg.code_address in specials.specials:
            log_msg.debug("{{{{{{{{{{{{{{{{{ SPECIALS")
            log_msg.debug(specials.specials[msg.code_address])
            log_msg.debug(msg.data)
            res, gas, dat = specials.specials[msg.code_address](ext, msg)
            log_msg.debug(res)
            log_msg.debug(gas)
            log_msg.debug(dat)
        else:
            log_msg.debug("[[[[[[[[[[[[[[[[ vm execute")
            log_msg.debug(code)
            res, gas, dat = vm.vm_execute(ext, msg, code)
            log_msg.debug(res)
            log_msg.debug(gas)
            log_msg.debug(dat)
        # gas = int(gas)
        # assert utils.is_numeric(gas)
        if trace_msg:
            log_msg.debug('MSG APPLIED', gas_remained=gas,
                          sender=encode_hex(msg.sender), to=encode_hex(msg.to), data=dat)
            if log_state.is_active('trace'):
                log_state.trace('MSG POST STATE SENDER', account=msg.sender.encode('hex'),
                                bal=ext.get_balance(msg.sender),
                                state=ext.log_storage(msg.sender))
                log_state.trace('MSG POST STATE RECIPIENT', account=msg.to.encode('hex'),
                                bal=ext.get_balance(msg.to),
                                state=ext.log_storage(msg.to))

        if res == 0:
            log_msg.debug('REVERTING')
            ext._block.revert(snapshot)

        return res, gas, dat
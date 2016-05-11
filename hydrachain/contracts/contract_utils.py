import os

import time
from ethereum import processblock
from ethereum._solidity import solc_wrapper
from ethereum.exceptions import InvalidTransaction
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms
from pyethapp.jsonrpc import data_encoder
from pyethapp.rpc_client import ABIContract

from hydrachain.contracts.contracts_settings import USER_REGISTRY_CONTRACT_INTERFACE


class ContractUtils:
    def __init__(self, app, log):
        self.contract = None

        self.app = app
        self.services = app.services
        self.stop = app.stop
        self.chainservice = app.services.chain
        self.chain = self.chainservice.chain
        self.coinbase = app.services.accounts.coinbase

        self.log = log

    def new_contract(self, address, sender=None):
        contract_interface = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), USER_REGISTRY_CONTRACT_INTERFACE)).read()
        self.contract = ABIContract(sender or self.coinbase, contract_interface, address, self.call, self.transact)

    @property
    def head_candidate(self):
        return self.chain.head_candidate

    def find_transaction(self, tx):
        try:
            t, block, index = self.chain.index.get_transaction(tx.hash)
        except:
            return {}
        return dict(tx=t, block=block, index=index)

    def transact(self, to, value=0, data='', sender=None, startgas=25000, gasprice=60 * denoms.shannon):
        sender = normalize_address(sender or self.coinbase)
        to = normalize_address(to, allow_blank=True)
        nonce = self.head_candidate.get_nonce(sender)
        tx = Transaction(nonce, gasprice, startgas, to, value, data)
        self.app.services.accounts.sign_tx(sender, tx)
        assert tx.sender == sender
        self.chainservice.add_transaction(tx)
        return tx

    def call(self, to, value=0, data='', sender=None, startgas=25000, gasprice=60 * denoms.shannon):
        sender = normalize_address(sender or self.coinbase)

        to = normalize_address(to, allow_blank=True)
        block = self.head_candidate

        state_root_before = block.state_root
        assert block.has_parent()
        # rebuild block state before finalization
        parent = block.get_parent()
        test_block = block.init_from_parent(parent, block.coinbase,
                                            timestamp=block.timestamp)
        for tx in block.get_transactions():
            success, output = processblock.apply_transaction(test_block, tx)
            assert success

        # apply transaction
        nonce = test_block.get_nonce(sender)
        tx = Transaction(nonce, gasprice, startgas, to, value, data)
        tx.sender = sender
        output = ''
        try:
            success, output = processblock.apply_transaction(test_block, tx)
        except InvalidTransaction:
            success = False
        assert block.state_root == state_root_before
        if success:
            return data_encoder(output)
        else:
            return False

    def deploy(self, solidity_file_path, contract_name, default_gas):
        solidity_code = open(solidity_file_path).read()
        binary = solc_wrapper.compile(solidity_code, contract_name=contract_name)
        tx = self.transact(sender=self.coinbase, data=binary, to='', startgas=default_gas)
        tx_info = {}

        while tx_info == {}:
            tx_info = self.find_transaction(tx)
            time.sleep(1)

        self.log.info(tx_info)

        if not self.chain.in_main_branch(tx_info['block']):
            return None
        # self.log.info("afterwards: block number {}".format(quantity_encoder(block.number)))

        return data_encoder(tx.creates) if tx.creates else None

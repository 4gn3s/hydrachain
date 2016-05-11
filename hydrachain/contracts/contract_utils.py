import os
import time

from ethereum import processblock
from ethereum._solidity import solc_wrapper
from ethereum.exceptions import InvalidTransaction
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms
from pyethapp.rpc_client import JSONRPCClient

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

    def create_contract_abi(self, contract_address):
        # contract_interface = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), USER_REGISTRY_CONTRACT_INTERFACE)).read()
        # self.contract = self.client.new_abi_contract(contract_interface, contract_address)
        pass

    @property
    def head_candidate(self):
        return self.chain.head_candidate

    def call(self, to, value=0, data='', sender=None, startgas=25000, gasprice=60 * denoms.shannon):
        sender = normalize_address(sender or self.coinbase)

        to = normalize_address(to, allow_blank=True)
        block = self.head_candidate
        self.log.info("head candid {}".format(block))
        state_root_before = block.state_root
        assert block.has_parent()
        # rebuild block state before finalization
        parent = block.get_parent()
        test_block = block.init_from_parent(parent, block.coinbase,
                                            timestamp=block.timestamp)
        for tx in block.get_transactions():
            success, output = processblock.apply_transaction(test_block, tx)
            assert success
        self.log.info("applying transaction")
        # apply transaction
        nonce = test_block.get_nonce(sender)
        tx = Transaction(nonce, gasprice, startgas, to, value, data)
        tx.sender = sender
        try:
            success, output = processblock.apply_transaction(test_block, tx)
            self.log.info("transaction applied")
        except InvalidTransaction:
            success = False
        assert block.state_root == state_root_before
        if success:
            return output
        else:
            return False

    def deploy(self, solidity_file_path, contract_name, default_gas):

        # compile solidity code to get the bytecode
        solidity_code = open(solidity_file_path).read()
        binary = solc_wrapper.compile(solidity_code, contract_name=contract_name)


        self.log.info("COINBASE {}".format(self.coinbase))
        # our send transaction
        res = self.call(sender=self.coinbase, data=binary, to='', startgas=default_gas)
        self.log.info(res)

        return res

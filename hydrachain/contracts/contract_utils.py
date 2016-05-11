import os
import time

from ethereum import processblock
from ethereum._solidity import solc_wrapper
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms
from pyethapp.rpc_client import JSONRPCClient

from hydrachain.contracts.contracts_settings import USER_REGISTRY_CONTRACT_INTERFACE


class ContractUtils:
    def __init__(self, services, jsonrpc_port=4000):
        self.client = JSONRPCClient(port=jsonrpc_port, print_communication=False)
        self.contract = None

        self.services = services
        self.chainservice = services[4]
        self.chain = self.chainservice.chain
        self.coinbase = services[1].coinbase

    def create_contract_abi(self, contract_address):
        contract_interface = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), USER_REGISTRY_CONTRACT_INTERFACE)).read()
        self.contract = self.client.new_abi_contract(contract_interface, contract_address)

    def get_transaction_info(self, eth_tx_hash):
        receipt = self.client.call('eth_getTransactionReceipt', eth_tx_hash)
        return receipt

    @property
    def head_candidate(self):
        return self.chain.head_candidate

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
        try:
            success, output = processblock.apply_transaction(test_block, tx)
        except processblock.InvalidTransaction:
            success = False
        assert block.state_root == state_root_before
        if success:
            return output
        else:
            return False

    def deploy(self, solidity_file_path, contract_name, deploy_gas):

        # compile solidity code to get the bytecode
        solidity_code = open(solidity_file_path).read()
        binary = solc_wrapper.compile(solidity_code, contract_name=contract_name)

        # our send transaction
        res = self.call(sender=self.client.coinbase, data=binary, to='')
        print(res)

        # wait for the transaction to be mined and accepted
        receipt = None
        while receipt is None:
            # Get transaction receipt to have the address of contract
            receipt = self.get_transaction_info(res.encode('hex'))
            print('eth_getTransactionReceipt returned {}'.format(receipt))
            time.sleep(1)

        # Get contract address from receipt
        contract_address = receipt['contractAddress']
        return contract_address

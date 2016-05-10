from ethereum import processblock
from ethereum.exceptions import InvalidTransaction
from ethereum.transactions import Transaction
from ethereum.utils import denoms
from pyethapp.console_service import normalize_address


class ContractManager:
    def __init__(self, services):
        self.chainservice = services[4]
        self.accountsservice = services[1]
        self.coinbase = self.accountsservice.coinbase

    def transact(self, to, value=0, data='', sender=None, startgas=25000, gasprice=60 * denoms.shannon):
        sender = normalize_address(sender or self.coinbase)
        to = normalize_address(to, allow_blank=True)
        nonce = self.chainservice.chain.head_candidate.get_nonce(sender)
        tx = Transaction(nonce, gasprice, startgas, to, value, data)
        self.accountsservice.sign_tx(sender, tx)
        assert tx.sender == sender
        self.chainservice.add_transaction(tx)
        return tx

    def call(self, to, value=0, data='', sender=None, startgas=25000, gasprice=60 * denoms.shannon):
        sender = normalize_address(sender or self.coinbase)
        to = normalize_address(to, allow_blank=True)
        block = self.chainservice.chain.head_candidate
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
        output = None
        try:
            success, output = processblock.apply_transaction(test_block, tx)
        except InvalidTransaction:
            success = False
        assert block.state_root == state_root_before
        if success:
            return output
        else:
            return False

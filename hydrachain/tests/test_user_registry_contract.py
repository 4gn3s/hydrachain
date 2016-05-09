import unittest
import os

from ethereum import tester
from ethereum import utils


class TestUserRegistryContract(unittest.TestCase):

    CONTRACT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../contracts/user_registry_contract.sol')

    @classmethod
    def setup_class(cls):
        cls.state = tester.state()
        code = open(cls.CONTRACT).read()
        cls.owner = tester.k0
        cls.someone_else = tester.k1
        cls.owner_address = tester.a0
        cls.someone_else_address = tester.a1
        cls.contract = cls.state.abi_contract(code,
                                              language='solidity',
                                              sender=cls.owner)
        cls.initial_admin_begin_block = 1
        cls.begin_block = 10
        cls.snapshot = cls.state.snapshot()


    def setUp(self):
        self.state.revert(self.snapshot)
        # fill the contract with some data here

    def test_initial_admin_set(self):
        self.assertEqual(self.contract.initialAdmin(), utils.encode_hex(self.owner_address))
        self.assertTrue(self.contract.isAuthorizedToTransact(self.owner_address, self.initial_admin_begin_block))

    def test_add_user_known_registrar_active(self):
        self.contract.addUser(tester.a9, self.begin_block)
        self.assertFalse(self.contract.isAuthorizedToTransact(tester.a9, self.begin_block - 1))
        self.assertTrue(self.contract.isAuthorizedToTransact(tester.a9, self.begin_block))
        self.assertTrue(self.contract.isAuthorizedToTransact(tester.a9, self.begin_block + 1))

    def test_add_user_known_registrar_not_active(self):
        # with self.assertRaises(TransactionFailed):
        #     self.contract.addUser(tester.a9, self.begin_block, sender=self.someone_else)
        pass

    def test_add_user_unknown_registrar(self):
        pass

    def test_add_user_already_removed(self):
        pass

    def test_remove_user_by_owner_active(self):
        pass

    def test_remove_user_by_owner_not_active(self):
        pass

    def test_remove_user_by_someone_else(self):
        pass

    def test_remove_user_non_existent(self):
        pass

    def test_remove_user_already_removed(self):
        pass

    def test_add_registrar_initial_admin(self):
        pass

    def test_add_registrar_known_parent_active(self):
        pass

    def test_add_registrar_known_parent_not_active(self):
        pass

    def test_add_registrar_unknown_parent(self):
        pass

    def test_add_registrar_already_removed(self):
        pass

    def test_remove_initial_admin_registrar(self):
        pass

    def test_remove_registrar_by_parent(self):
        pass

    def test_remove_registrar_by_someone_else(self):
        pass

    def test_remove_registrar_already_removed(self):
        pass

    def test_can_transact_unknown_user(self):
        pass

    def test_can_transact_known_user(self):
        pass

    def test_can_transact_unknown_registrar(self):
        pass

    def test_can_transact_known_registrar(self):
        pass

    def test_can_transact_older_block(self):
        pass

    def test_can_transact_newer_block(self):
        pass
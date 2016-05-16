import unittest
import os

from ethereum import tester
from ethereum import utils
from ethereum.tester import TransactionFailed


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
        cls.contract = cls.state.abi_contract(code, language='solidity', sender=cls.owner)
        cls.initial_admin_begin_block = 1
        cls.begin_block = 10
        cls.user_removed = tester.a3
        cls.user_active = tester.a4
        cls.registrar_removed = tester.a5
        cls.registrar_removed_k = tester.k5
        cls.registrar_parent = tester.a6
        cls.registrar_parent_k = tester.k6
        cls.registrar_child = tester.a7
        cls.registrar_child_k = tester.k7
        cls.temporary_account = tester.a8
        cls.temporary_account_k = tester.k8
        cls.snapshot = cls.state.snapshot()

    def setUp(self):
        self.state.revert(self.snapshot)
        # add some test users/registrars
        self.contract.addUser(self.user_active, self.begin_block)
        self.contract.addRegistrar(self.registrar_parent, self.begin_block)
        self.contract.addRegistrar(self.registrar_child, self.begin_block, sender=self.registrar_parent_k)
        # add and remove a user
        self.contract.addUser(self.user_removed, self.begin_block)
        self.contract.removeUser(self.user_removed)
        # add and remove a registrar
        self.contract.addRegistrar(self.registrar_removed, self.begin_block)
        self.contract.removeRegistrar(self.registrar_removed)

    def test_initial_admin_set(self):
        self.assertEqual(self.contract.initialAdmin(), utils.encode_hex(self.owner_address))
        self.assertTrue(self.contract.isAuthorizedToTransact(self.owner_address, self.initial_admin_begin_block))

    def test_add_user_known_registrar_active(self):
        self.assertTrue(self.contract.addUser(self.temporary_account, self.begin_block))

    def test_add_user_older_than_parent(self):
        self.assertFalse(self.contract.addUser(self.temporary_account, self.initial_admin_begin_block-1))

    def test_add_user_known_registrar_not_active(self):
        with self.assertRaises(TransactionFailed):
            self.contract.addUser(self.temporary_account, self.begin_block, sender=self.registrar_removed_k)

    def test_add_user_unknown_registrar(self):
        with self.assertRaises(TransactionFailed):
            self.contract.addUser(self.temporary_account, self.begin_block, sender=self.someone_else)

    def test_add_user_already_removed(self):
        self.assertFalse(self.contract.addUser(self.user_removed, self.begin_block))

    def test_remove_user_by_owner_active(self):
        self.assertTrue(self.contract.removeUser(self.user_active))

    def test_remove_user_by_owner_not_active(self):
        with self.assertRaises(TransactionFailed):
            self.contract.removeUser(self.user_active, sender=self.registrar_removed_k)

    def test_remove_user_by_someone_else(self):
        with self.assertRaises(TransactionFailed):
            self.contract.removeUser(self.user_active, sender=self.someone_else)

    def test_remove_user_non_existent(self):
        self.assertFalse(self.contract.removeUser(self.temporary_account))

    def test_remove_user_already_removed(self):
        self.assertTrue(self.contract.removeUser(self.user_removed))

    def test_add_registrar_older_than_parent(self):
        self.assertFalse(self.contract.addRegistrar(self.temporary_account, self.initial_admin_begin_block - 1))

    def test_add_registrar_initial_admin(self):
        self.assertTrue(self.contract.addRegistrar(self.temporary_account, self.begin_block, sender=self.owner))

    def test_add_registrar_known_parent_active(self):
        self.assertTrue(self.contract.addRegistrar(self.temporary_account, self.begin_block, sender=self.registrar_child_k))

    def test_add_registrar_known_parent_not_active(self):
        with self.assertRaises(TransactionFailed):
            self.contract.addRegistrar(self.temporary_account, self.begin_block, sender=self.registrar_removed_k)

    def test_add_registrar_unknown_parent(self):
        with self.assertRaises(TransactionFailed):
            self.contract.addRegistrar(self.temporary_account, self.begin_block, sender=self.temporary_account_k)

    def test_add_registrar_already_removed(self):
        self.assertFalse(self.contract.addRegistrar(self.registrar_removed, self.begin_block))

    def test_remove_initial_admin_registrar(self):
        self.assertFalse(self.contract.removeRegistrar(self.owner_address))

    def test_remove_registrar_by_parent(self):
        self.assertTrue(self.contract.removeRegistrar(self.registrar_child, sender=self.registrar_parent_k))

    def test_remove_registrar_by_someone_else(self):
        with self.assertRaises(TransactionFailed):
            self.contract.removeRegistrar(self.registrar_child, sender=self.temporary_account_k)

    def test_remove_registrar_already_removed(self):
        self.assertTrue(self.contract.removeRegistrar(self.registrar_removed))

    def test_can_transact_unknown_user(self):
        self.assertFalse(self.contract.isAuthorizedToTransact(self.temporary_account, self.begin_block))

    def test_can_transact_known_user(self):
        self.assertTrue(self.contract.isAuthorizedToTransact(self.user_active, self.begin_block))

    def test_can_transact_known_registrar(self):
        self.assertTrue(self.contract.isAuthorizedToTransact(self.registrar_parent, self.begin_block))

    def test_can_transact_older_block(self):
        self.assertFalse(self.contract.isAuthorizedToTransact(self.user_active, self.begin_block - 1))

    def test_can_transact_newer_block(self):
        self.assertTrue(self.contract.isAuthorizedToTransact(self.user_active, self.begin_block + 1))

import unittest

from ethereum import tester

import hydrachain.native_contracts as nc
from hydrachain.contracts.user_registry_contract import UserRegistryContract
from hydrachain.nc_utils import ERROR, OK


class TestUserRegistryContract(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        cls.state = tester.state()

        cls.owner = tester.k0
        cls.someone_else = tester.k1
        cls.owner_address = tester.a0
        cls.someone_else_address = tester.a1

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

        nc.registry.register(UserRegistryContract)
        user_registry_address = nc.tester_create_native_contract_instance(cls.state, cls.owner, UserRegistryContract)
        cls.contract_as_owner = nc.tester_nac(cls.state, cls.owner, user_registry_address)
        cls.contract_as_someone_else = nc.tester_nac(cls.state, cls.someone_else, user_registry_address)
        cls.contract_as_registrar_parent = nc.tester_nac(cls.state, cls.registrar_parent_k, user_registry_address)
        cls.contract_as_registrar_child = nc.tester_nac(cls.state, cls.registrar_child_k, user_registry_address)
        cls.contract_as_registrar_removed = nc.tester_nac(cls.state, cls.registrar_removed_k, user_registry_address)
        cls.contract_as_temporary_account = nc.tester_nac(cls.state, cls.temporary_account_k, user_registry_address)

        cls.snapshot = cls.state.snapshot()

    @classmethod
    def tearDownClass(cls):
        nc.registry.unregister(UserRegistryContract)

    def setUp(self):
        self.state.revert(self.snapshot)
        self.contract_as_owner.init(self.owner_address)
        assert self.contract_as_owner.get_registrar_begin(self.contract_as_owner.get_owner()) == 1
        # add some test users/registrars
        self.contract_as_owner.add_user(self.user_active, self.begin_block)
        self.contract_as_owner.add_registrar(self.registrar_parent, self.begin_block)
        self.contract_as_registrar_parent.add_registrar(self.registrar_child, self.begin_block)
        # add and remove a user
        self.contract_as_owner.add_user(self.user_removed, self.begin_block)
        self.contract_as_owner.remove_user(self.user_removed)
        # add and remove a registrar
        self.contract_as_owner.add_registrar(self.registrar_removed, self.begin_block)
        self.contract_as_owner.remove_registrar(self.registrar_removed)

    def test_initial_admin_set(self):
        self.assertEqual(self.contract_as_owner.get_owner(), self.owner_address)
        self.assertTrue(self.contract_as_owner.is_authorized(self.owner_address, self.initial_admin_begin_block))

    def test_add_user_known_registrar_active(self):
        self.assertEqual(self.contract_as_owner.add_user(self.temporary_account, self.begin_block), OK)

    def test_add_user_older_than_parent(self):
        self.assertEqual(self.contract_as_owner.add_user(self.temporary_account, self.initial_admin_begin_block-1), ERROR)

    def test_add_user_known_registrar_not_active(self):
        self.assertEqual(self.contract_as_registrar_removed.add_user(self.temporary_account, self.begin_block), ERROR)

    def test_add_user_unknown_registrar(self):
        self.assertEqual(self.contract_as_someone_else.add_user(self.temporary_account, self.begin_block), ERROR)

    def test_add_user_already_removed(self):
        self.assertEqual(self.contract_as_owner.add_user(self.user_removed, self.begin_block), ERROR)

    def test_remove_user_by_owner_active(self):
        self.assertEqual(self.contract_as_owner.remove_user(self.user_active), OK)

    def test_remove_user_by_owner_not_active(self):
        self.assertEqual(self.contract_as_registrar_removed.remove_user(self.user_active), ERROR)

    def test_remove_user_by_someone_else(self):
        self.assertEqual(self.contract_as_someone_else.remove_user(self.user_active), ERROR)

    def test_remove_user_non_existent(self):
        self.assertEqual(self.contract_as_owner.remove_user(self.temporary_account), ERROR)

    def test_remove_user_already_removed(self):
        self.assertEqual(self.contract_as_owner.remove_user(self.user_removed), OK)

    def test_add_registrar_older_than_parent(self):
        self.assertEqual(self.contract_as_owner.add_registrar(self.temporary_account, self.initial_admin_begin_block - 1), ERROR)

    def test_add_registrar_initial_admin(self):
        self.assertEqual(self.contract_as_owner.add_registrar(self.temporary_account, self.begin_block), OK)

    def test_add_registrar_known_parent_active(self):
        self.assertEqual(self.contract_as_registrar_child.add_registrar(self.temporary_account, self.begin_block), OK)

    def test_add_registrar_known_parent_not_active(self):
        self.assertEqual(self.contract_as_registrar_removed.add_registrar(self.temporary_account, self.begin_block), ERROR)

    def test_add_registrar_unknown_parent(self):
        self.assertEqual(self.contract_as_temporary_account.add_registrar(self.temporary_account, self.begin_block), ERROR)

    def test_add_registrar_already_removed(self):
        self.assertEqual(self.contract_as_owner.add_registrar(self.registrar_removed, self.begin_block), ERROR)

    def test_remove_initial_admin_registrar(self):
        self.assertEqual(self.contract_as_owner.remove_registrar(self.owner_address), ERROR)

    def test_remove_registrar_by_parent(self):
        self.assertEqual(self.contract_as_registrar_parent.remove_registrar(self.registrar_child), OK)

    def test_remove_registrar_by_someone_else(self):
        self.assertEqual(self.contract_as_temporary_account.remove_registrar(self.registrar_child), ERROR)

    def test_remove_registrar_already_removed(self):
        self.assertEqual(self.contract_as_owner.remove_registrar(self.registrar_removed), OK)

    def test_can_transact_unknown_user(self):
        self.assertFalse(self.contract_as_owner.is_authorized(self.temporary_account, self.begin_block))

    def test_can_transact_known_user(self):
        self.assertTrue(self.contract_as_owner.is_authorized(self.user_active, self.begin_block))

    def test_can_transact_known_registrar(self):
        self.assertTrue(self.contract_as_owner.is_authorized(self.registrar_parent, self.begin_block))

    def test_can_transact_older_block(self):
        self.assertFalse(self.contract_as_owner.is_authorized(self.user_active, self.begin_block - 1))

    def test_can_transact_newer_block(self):
        self.assertTrue(self.contract_as_owner.is_authorized(self.user_active, self.begin_block + 1))
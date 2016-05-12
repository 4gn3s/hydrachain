from ethereum import tester
import hydrachain.native_contracts as nc
import ethereum.slogging as slogging

from hydrachain.contracts.user_registry_contract import UserRegistryContract

log = slogging.get_logger('test.contracts.user_registry')


def test_nc_instance():
    state = tester.state()
    creator_address = tester.a0
    creator_key = tester.k0

    # nc.registry.register(UserRegistryContract)

    # Create proxy
    user_registry_address = nc.tester_create_native_contract_instance(state, creator_key, UserRegistryContract)
    contract_as_creator = nc.tester_nac(state, creator_key, user_registry_address)

    contract_as_creator.init()
    assert contract_as_creator.is_authorized(tester.a1, 11) == 0
    contract_as_creator.add_user(tester.a1, 10)
    assert contract_as_creator.is_authorized(tester.a1, 11) == 1
    # nc.registry.unregister(UserRegistryContract)
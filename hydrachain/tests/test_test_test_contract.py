from ethereum import tester
import hydrachain.native_contracts as nc
import ethereum.slogging as slogging

from hydrachain.contracts.test_test_contract import FungibleK

log = slogging.get_logger('test.fungible')


def test_fungible_instance():
    state = tester.state()
    creator_address = tester.a0
    creator_key = tester.k0

    nc.registry.register(FungibleK)

    # Create proxy
    EUR_address = nc.tester_create_native_contract_instance(state, creator_key, FungibleK)
    fungible_as_creator = nc.tester_nac(state, creator_key, EUR_address)
    # Initalize fungible with a fixed quantity of fungibles.
    fungible_total = 1000000
    fungible_as_creator.init(fungible_total)
    assert fungible_as_creator.balanceOf(creator_address) == fungible_total
    nc.registry.unregister(FungibleK)

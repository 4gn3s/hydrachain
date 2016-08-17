from ethereum.tester import accounts
from examples.native.fungible.fungible_contract import Fungible

from hydrachain.nc_utils import create_contract_instance, OK, wait_next_block_factory
import hydrachain.native_contracts as nc


# USAGE:
# 1. if there is a datadir, remove it:
# rm -r datadir
#
# 2. run hydrachain:
# hydrachain -d datadir runmultiple --num_validators=2 --seed=42
#
# 3. after 10 blocks, click Ctrl + C followed by Enter, to enter the console and do:
# eth.chain.head.get_balance(eth.coinbase) # to make sure there are funds
# from hydrachain.nc_interaction import *
# try_interact(eth, eth.coinbase)
# lastlog(1000) # to read the logs


def try_interact(app, coinbase):
    nc.registry.register(Fungible)
    tx_reg_address = create_contract_instance(app, coinbase, Fungible)
    proxy = nc.chain_nac_proxy(app.services.chain.chain, coinbase, tx_reg_address)

    total = 10000
    transfer_amount = 10

    proxy.init(total)

    wait_next_block_factory(app)()

    assert proxy.totalSupply() == total
    assert proxy.balanceOf(coinbase) == total
    assert proxy.transfer(accounts[0], transfer_amount) == OK
    assert proxy.balanceOf(coinbase) == total - transfer_amount
    assert proxy.balanceOf(accounts[0]) == transfer_amount


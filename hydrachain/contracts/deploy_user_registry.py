import os

from devp2p.discovery import NodeDiscovery
from devp2p.peermanager import PeerManager
from pyethapp.accounts import AccountsService
from pyethapp.console_service import Console
from pyethapp.db_service import DBService
from pyethapp.eth_service import ChainService
from pyethapp.jsonrpc import JSONRPCServer

from hydrachain.contracts.contract_utils import ContractUtils
from hydrachain.contracts.contracts_settings import USER_REGISTRY_CONTRACT_FILE, USER_REGISTRY_CONTRACT_NAME, \
    CONTRACT_DEPLOYMENT_GAS


services = [DBService,
            AccountsService,
            NodeDiscovery,
            PeerManager,
            ChainService,
            JSONRPCServer,
            Console]


if __name__ == '__main__':
    contract_full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), USER_REGISTRY_CONTRACT_FILE)
    contract_address = ContractUtils(services).deploy(contract_full_path, USER_REGISTRY_CONTRACT_NAME, CONTRACT_DEPLOYMENT_GAS)
    print(contract_address)
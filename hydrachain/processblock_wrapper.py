from ethereum.exceptions import UnsignedTransaction, InvalidTransaction
from ethereum.processblock import validate_transaction

# from hydrachain.contracts.contracts_settings import USER_REGISTRY_CONTRACT_INTERFACE
from hydrachain.contracts.contract_utils import ContractManager


class UnauthorizedTransaction(InvalidTransaction):
    pass


class ProcessblockWrapper:
    def __init__(self, services):
        self.services = services
        self.contract_manager = ContractManager(services)

    @staticmethod
    def validate_transaction_wrapper(block, tx):
        if not tx.sender:  # sender is set and validated on Transaction initialization
            raise UnsignedTransaction(tx)

        # TODO: call self.contract_manager.call with isAuthorizedToTransact

        # contract_address = block.config['hdc']["user_registry_contract_address"]
        #
        # contract_interface = open(USER_REGISTRY_CONTRACT_INTERFACE).read()
        # contract = client.new_abi_contract(contract_interface, contract_address)
        #
        # if not contract.isAuthorizedToTransact(tx.sender, block.number):
        #     raise UnauthorizedTransaction(tx)

        return validate_transaction(block, tx)

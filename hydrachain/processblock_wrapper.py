from ethereum import slogging
from ethereum.exceptions import UnsignedTransaction, InvalidTransaction
from ethereum.processblock import validate_transaction

from hydrachain.contracts.contract_utils import ContractUtils

log = slogging.get_logger('app')


class UnauthorizedTransaction(InvalidTransaction):
    pass


class ProcessblockWrapper:
    @staticmethod
    def validate_transaction_wrapper(block, tx):
        if not tx.sender:  # sender is set and validated on Transaction initialization
            raise UnsignedTransaction(tx)

        contract_address = block.config['hdc']["user_registry_contract_address"]

        if contract_address:
            contract_utils = ContractUtils(block.config['jsonrpc']['listen_port'])
            contract_utils.create_contract_abi(contract_address)
            if not contract_utils.contract.isAuthorizedToTransact(tx.sender, block.number):
                raise UnauthorizedTransaction(tx)

        return validate_transaction(block, tx)

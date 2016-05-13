from ethereum import slogging
from ethereum.exceptions import InvalidTransaction
from ethereum.processblock import validate_transaction
from ethereum.exceptions import UnsignedTransaction

from ethereum.slogging import get_logger
log_tx = get_logger('eth.pb.tx')

log = slogging.get_logger('app')


class UnauthorizedTransaction(InvalidTransaction):
    pass


class ProcessblockWrapper:
    @staticmethod
    def validate_transaction_wrapper(block, tx):
        if not tx.sender:  # sender is set and validated on Transaction initialization
            raise UnsignedTransaction(tx)

        contract_address = None
        # log.info(block.config)
        if 'hdc' in block.config:
            if 'user_registry_contract_address' in block.config['hdc']:
                contract_address = block.config['hdc']["user_registry_contract_address"]

        if contract_address:
            print("validating tx AUTH AUTH ATUH")
            # log.info("validating if transaction sender is authorized")
            # contract_utils = ContractUtils(block.config['jsonrpc']['listen_port'])
            # contract_utils.new_contract(contract_address)
            # if not contract_utils.contract.isAuthorizedToTransact(tx.sender, block.number):
            #     raise UnauthorizedTransaction(tx)

        return validate_transaction(block, tx)

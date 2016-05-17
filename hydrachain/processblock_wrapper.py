from ethereum import slogging
from ethereum import utils
from ethereum import vm as vm
from ethereum.exceptions import InvalidTransaction
from ethereum.exceptions import UnsignedTransaction
from ethereum.processblock import apply_msg, lazy_safe_encode, VMExt
from ethereum import specials
from ethereum.transactions import Transaction
from rlp.utils_py2 import ascii_chr, safe_ord

from hydrachain import native_contracts as nc
from hydrachain.native_contracts import NativeABIContract, abi_encode_args, abi_decode_return_vals

log = slogging.get_logger('app_processblock_wrapper')


class UnauthorizedTransaction(InvalidTransaction):
    pass


def free_call(block, tx):
    message_data = vm.CallData([safe_ord(x) for x in tx.data], 0, len(tx.data))
    message = vm.Message(tx.sender, tx.to, tx.value, 0, message_data, code_address=tx.to)

    # MESSAGE
    ext = VMExt(block, tx)
    code = ext.get_code(message.code_address)

    snapshot = ext._block.snapshot()
    if message.transfers_value:
        if not ext._block.transfer_value(message.sender, message.to, message.value):
            log.debug('MSG TRANSFER FAILED', have=ext.get_balance(message.to),
                          want=message.value)
            return 1, message.gas, []
    # Main loop
    if message.code_address in specials.specials:
        result, gas, data = specials.specials[message.code_address](ext, message)
    else:
        result, gas, data = vm.vm_execute(ext, message, code)

    if result == 0:
        log.debug('REVERTING')
    ext._block.revert(snapshot)

    # log.debug('_res_', result=result, gas_remained=gas_remained, data=lazy_safe_encode(data))
    if result:
        return b''.join(map(ascii_chr, data))


def contract_proxy(block, sender, contract_address, value=0):
    "create an object which acts as a proxy for the contract on the chain"
    contact = nc.registry[contract_address].im_self
    assert issubclass(contact, NativeABIContract)

    def mk_method(method):
        def m(s, *args):
            data = abi_encode_args(method, args)
            log.info(data)
            startgas = block.gas_limit - block.gas_used
            gasprice = 0
            nonce = block.get_nonce(sender)
            tx = Transaction(nonce, gasprice, startgas, contract_address, value, data)
            tx.sender = sender
            output = free_call(block, tx)
            if output is not None:
                return abi_decode_return_vals(method, output)
        return m

    class cproxy(object):
        pass
    for m in contact._abi_methods():
        setattr(cproxy, m.__func__.func_name, mk_method(m))

    return cproxy()


def validate_transaction_wrapper(validate_transaction):
    def validate_with_user_registry(block, tx):
        if not tx.sender:  # sender is set and validated on Transaction initialization
            raise UnsignedTransaction(tx)

        if 'hdc' in block.config:
            if 'user_registry_contract_address' in block.config['hdc']:
                if block.config['hdc']['user_registry_contract_address'] != '':
                    log.info("validating the transaction in processblock wrapper")
                    contract_address = utils.decode_hex(block.config['hdc']["user_registry_contract_address"])
                    contract_object = contract_proxy(block, tx.sender, contract_address)
                    if not contract_object.is_authorized(tx.sender, block.number):
                        log.info("validation in processblock wrapper failed")
                        raise UnauthorizedTransaction(tx)

        return validate_transaction(block, tx)

    return validate_with_user_registry

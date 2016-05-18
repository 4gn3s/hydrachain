from ethereum import slogging
from ethereum import specials
from ethereum import utils
from ethereum import vm as vm
from ethereum.exceptions import InvalidTransaction
from ethereum.exceptions import UnsignedTransaction
from ethereum.processblock import VMExt
from rlp.utils_py2 import safe_ord

from hydrachain import native_contracts as nc
from hydrachain.native_contracts import NativeABIContract, abi_encode_args, abi_decode_return_vals

log = slogging.get_logger('app_processblock_wrapper')


class UnauthorizedTransaction(InvalidTransaction):
    pass


def call(block, tx, address, method, *args, **kwargs):
    if address not in nc.registry:
        raise KeyError("native contract missing from registry")
    klass = nc.registry[address].im_self
    methods = klass._abi_methods()
    methods_dict = {}
    for m in methods:
        method_info = klass._get_method_abi(m)
        methods_dict[method_info['name']] = method_info
    abi_contract_method = methods_dict[method]['method']
    data = abi_encode_args(abi_contract_method, args)
    data = vm.CallData(memoryview(data).tolist())
    value = kwargs.get('value', 0)
    startgas = block.gas_limit - block.gas_used
    nonce = block.get_nonce(tx.sender)
    msg = vm.Message(tx.sender, address, value, startgas, data,
                     nonce, code_address=address)
    ext = VMExt(block, tx)
    success, gas, out = ext.msg(msg)
    assert success
    out = ''.join(chr(x) for x in out)
    return abi_decode_return_vals(abi_contract_method, out)


def validate_transaction_wrapper(validate_transaction):
    def validate_with_user_registry(block, tx):
        if not tx.sender:  # sender is set and validated on Transaction initialization
            raise UnsignedTransaction(tx)

        if 'hdc' in block.config:
            if 'user_registry_contract_address' in block.config['hdc']:
                if block.config['hdc']['user_registry_contract_address'] != '':
                    log.info("validating the transaction in processblock wrapper")
                    contract_address = utils.decode_hex(block.config['hdc']["user_registry_contract_address"])
                    if not call(block, tx, contract_address, 'is_authorized', tx.sender, block.number):
                        log.info("validation in processblock wrapper failed")
                        raise UnauthorizedTransaction(tx)

        return validate_transaction(block, tx)

    return validate_with_user_registry

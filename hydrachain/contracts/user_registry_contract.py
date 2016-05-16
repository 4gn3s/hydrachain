from ethereum import slogging
import ethereum.utils as utils

import hydrachain.native_contracts as nc
from hydrachain.nc_utils import STATUS, FORBIDDEN, isaddress, OK, ERROR

log = slogging.get_logger('contracts.user_registry')


class UserRegistryContract(nc.NativeContract):
    address = utils.int_to_addr(5000)
    owner = nc.Scalar('address')
    users_registrar_address = nc.Dict('address')
    users_begin_block = nc.IterableDict('int256')
    registrars_super_registrar = nc.Dict('address')
    registrars_begin_block=nc.IterableDict('int256')

    def init(ctx, _origin_account='address', returns=STATUS):
        if isaddress(ctx.owner):
            return FORBIDDEN
        ctx.owner = ctx.tx_origin
        ctx.registrars_super_registrar[ctx.tx_origin] = _origin_account
        ctx.registrars_begin_block[ctx.tx_origin] = 1
        return OK

    def add_user(ctx, _user_address='address', _begin_block='int256', returns=STATUS):
        # if we know the registrar if it is in the register and it has not been removed
        if ctx.registrars_begin_block[ctx.msg_sender] != 0 and ctx.registrars_begin_block[ctx.msg_sender] != -1:
            # first check if the address has not been removed already
            if ctx.users_begin_block[_user_address] != -1:
                # don't add children with lower begin block than parent
                if ctx.registrars_begin_block[ctx.msg_sender] <= _begin_block:
                    ctx.users_registrar_address[_user_address] = ctx.msg_sender
                    ctx.users_begin_block[_user_address] = _begin_block
                    return OK
        return ERROR

    def add_registrar(ctx, _registrar_address='address', _begin_block='int256', returns=STATUS):
        # if we know the registrar if it is in the register and it has not been removed
        if ctx.registrars_begin_block[ctx.msg_sender] != 0 and ctx.registrars_begin_block[ctx.msg_sender] != -1:
            # first check if the address has not been removed already
            if ctx.registrars_begin_block[_registrar_address] != -1:
                # don't add children with lower begin block than parent
                if ctx.registrars_begin_block[ctx.msg_sender] <= _begin_block:
                    ctx.registrars_begin_block[_registrar_address] = _begin_block
                    ctx.registrars_super_registrar[_registrar_address] = ctx.msg_sender
                    return OK
        return ERROR

    def remove_user(ctx, _user_address='address', returns=STATUS):
        # if we know the registrar if it is in the register and it has not been removed
        if ctx.registrars_begin_block[ctx.msg_sender] != 0 and ctx.registrars_begin_block[ctx.msg_sender] != -1:
            if ctx.users_registrar_address[_user_address] == ctx.msg_sender:
                # if the user owns the entry
                ctx.users_begin_block[_user_address] = -1
                return OK
        return ERROR

    def remove_registrar(ctx, _registrar_address='address', returns=STATUS):
        # if we know the registrar if it is in the register and it has not been removed
        if ctx.registrars_begin_block[ctx.msg_sender] != 0 and ctx.registrars_begin_block[ctx.msg_sender] != -1:
            # if the user owns the entry
            if ctx.registrars_super_registrar[_registrar_address] == ctx.msg_sender:
                # if we're not trying to remove the initial registrar
                if _registrar_address != ctx.owner:
                    ctx.registrars_begin_block[_registrar_address] = -1
                    return OK
        return ERROR

    @nc.constant
    def is_authorized(ctx, _sender_address='address', _current_block='int256', returns='uint16'):
        # When a transaction is added to the block, it is checked if the
        # sender_address is in users/registrars and current block_height must be >= begin_block
        if ctx.users_begin_block[_sender_address] != 0 and ctx.users_begin_block[_sender_address] != -1:
            if ctx.users_begin_block[_sender_address] <= _current_block:
                return 1
        if ctx.registrars_begin_block[_sender_address] != 0 and ctx.registrars_begin_block[_sender_address] != -1:
            if ctx.registrars_begin_block[_sender_address] <= _current_block:
                return 1
        return 0

    @nc.constant
    def get_owner(ctx, returns='address'):
        return ctx.owner

    @nc.constant
    def get_registrar_begin(ctx, _address='address', returns='int256'):
        return ctx.registrars_begin_block[_address]

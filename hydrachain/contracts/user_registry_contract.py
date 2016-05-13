from ethereum import slogging
import ethereum.utils as utils

import hydrachain.native_contracts as nc
from hydrachain.nc_utils import STATUS, FORBIDDEN, isaddress, OK, ERROR

log = slogging.get_logger('contracts.user_registry')


class UserRegistryContract(nc.NativeContract):
    address = utils.int_to_addr(5000)
    owner = nc.Scalar('address')
    users = nc.Dict(
        nc.Struct(
            registrar_address=nc.List('address'),
            begin_block=nc.Scalar('int32')
        )
    )
    registrars = nc.Dict(
        nc.Struct(
            super_registrar=nc.List('address'),
            begin_block=nc.Scalar('int32')
        )
    )

    def init(ctx, returns=STATUS):
        log.info('UserRegistryContract init')
        if isaddress(ctx.owner):
            return FORBIDDEN
        ctx.owner = ctx.tx_origin
        ctx.registrars[ctx.tx_origin][ctx.tx_origin] = 1
        return OK

    def add_user(ctx, _user_address='address', _begin_block='int256', returns=STATUS):
        # if we know the registrar if it is in the register and it has not been removed
        if ctx.registrars[ctx.msg_sender] != 0 and ctx.registrars[ctx.msg_sender].begin_block != -1:
            # first check if the address has not been removed already
            if ctx.users[_user_address].begin_block != -1:
                # don't add children with lower begin block than parent
                if ctx.registrars[ctx.msg_sender].begin_block <= _begin_block:
                    ctx.users[_user_address].registrar_address = ctx.msg_sender
                    ctx.users[_user_address].begin_block = _begin_block
                    return OK
        return ERROR

    def add_registrar(ctx, _registrar_address='address', _begin_block='int256', returns=STATUS):
        # if we know the registrar if it is in the register and it has not been removed
        if ctx.registrars[ctx.msg_sender] != 0 and ctx.registrars[ctx.msg_sender].begin_block != -1:
            # first check if the address has not been removed already
            if ctx.registrars[_registrar_address].begin_block != -1:
                # don't add children with lower begin block than parent
                if ctx.registrars[ctx.msg_sender].begin_block <= _begin_block:
                    ctx.registrars[_registrar_address].begin_block = _begin_block
                    ctx.registrars[_registrar_address].super_registrar = ctx.msg_sender
                    return OK
        return ERROR

    def remove_user(ctx, _user_address='address', returns='int32'):
        # if we know the registrar if it is in the register and it has not been removed
        if ctx.registrars[ctx.msg_sender] != 0 and ctx.registrars[ctx.msg_sender].begin_block != -1:
            if ctx.users[_user_address].registrar_address == ctx.msg_sender:
                # if the user owns the entry
                ctx.users[_user_address].begin_block = -1
                return 1
        return 0

    def remove_registrar(ctx, _registrar_address='address', returns='int32'):
        # if we know the registrar if it is in the register and it has not been removed
        if ctx.registrars[ctx.msg_sender] != 0 and ctx.registrars[ctx.msg_sender].begin_block != -1:
            if ctx.registrars[_registrar_address].registrarAddress == ctx.msg_sender:
                # if the user owns the entry
                if _registrar_address != ctx.owner:
                    ctx.registrars[_registrar_address].beginBlock = -1
                    return 1
        return 0

    # @nc.constant
    # def is_authorized(ctx, _sender_address, _current_block, returns='uint16'):
    #     # When a transaction is added to the block, it is checked if the
    #     # sender_address is in users/registrars and current block_height must be >= begin_block
    #     if ctx.users[_sender_address] != 0 and ctx.users[_sender_address].begin_block != -1:
    #             if ctx.users[_sender_address].begin_block <= _current_block:
    #                 return 1
    #     if ctx.registrars[_sender_address] != 0 and ctx.registrars[_sender_address].begin_block != -1:
    #             if ctx.registrars[_sender_address].begin_block <= _current_block:
    #                 return 1
    #     return 0

    @nc.constant
    def get_users_parent(ctx, _user_address):
        return ctx.users[_user_address].registrar_address

    @nc.constant
    def get_users_begin_block(ctx, _user_address):
        return ctx.users[_user_address].begin_block

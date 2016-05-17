from ethereum import slogging
import ethereum.utils as utils
import hydrachain.native_contracts as nc

from hydrachain.nc_utils import FORBIDDEN, STATUS
from hydrachain.nc_utils import OK, isaddress


log = slogging.get_logger('contracts.test_contract')


class TestContract(nc.NativeContract):
    address = utils.int_to_addr(5000)
    owner = nc.Scalar('address')
    registrars = nc.Dict(
        # nc.Struct(
        #     x=nc.Scalar('address'),
        #     y=nc.Scalar('int256')
        # )
        'uint256'
    )
    stru = nc.Struct(x=nc.Scalar('uint16'), y=nc.Scalar('uint16'))

    def init(ctx, _initial_begin='uint256', returns=STATUS):
        log.info("test contract init")
        if isaddress(ctx.owner):
            return FORBIDDEN
        ctx.owner = ctx.tx_origin
        ctx.registrars[ctx.tx_origin] = _initial_begin
        ctx.stru.x = 11
        ctx.stru.y = 12
        return OK


    @nc.constant
    def begin(ctx, _address='address', returns='uint256'):
        return ctx.registrars[_address]

    @nc.constant
    def strget(ctx, returns='uint16'):
        return ctx.stru.x
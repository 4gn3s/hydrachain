from ethereum import slogging
import ethereum.utils as utils
import hydrachain.native_contracts as nc

from hydrachain.nc_utils import FORBIDDEN, STATUS
from hydrachain.nc_utils import OK, isaddress


log = slogging.get_logger('contracts.test_contract')


class TestContract(nc.NativeContract):
    address = utils.int_to_addr(5000)
    owner = nc.Scalar('address')

    def init(ctx, returns=STATUS):
        log.info("test contract init")
        if isaddress(ctx.owner):
            return FORBIDDEN
        ctx.owner = ctx.tx_origin
        return OK

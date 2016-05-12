import unittest

from ethereum import tester


class TestSolidityInteraction(unittest.TestCase):

    CONTRACT_CODE = """
    contract NameReg  {
           event AddressRegistered(bytes32 indexed name, address indexed account);
           mapping (address => bytes32) toName;

           function register(bytes32 name) {
                   toName[msg.sender] = name;
                   AddressRegistered(name, msg.sender);
           }

           function resolve(address addr) constant returns (bytes32 name) {
                   return toName[addr];
           }
    }
    """

    @classmethod
    def setup_class(cls):
        cls.state = tester.state()
        cls.owner = tester.k0
        cls.owner_account = tester.a0
        cls.contract = cls.state.abi_contract(cls.CONTRACT_CODE, language='solidity', sender=cls.owner)
        cls.snapshot = cls.state.snapshot()

    def setUp(self):
        self.state.revert(self.snapshot)

    def test_write_read(self):
        logs = []
        self.state.block.log_listeners.append(lambda x: logs.append(self.contract._translator.listen(x)))
        name = 'alice'
        self.contract.register(name)
        self.assertEqual(len(logs), 1)
        self.assertDictEqual(logs[0], {"_event_type": b"AddressRegistered", "account": self.owner_account.encode('hex'), "name": name+"\x00"*(32-len(name))})
        self.assertIsNotNone(self.contract.resolve(self.owner_account))

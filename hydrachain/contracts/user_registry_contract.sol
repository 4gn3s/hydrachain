contract UserRegistryContract {

    struct Registrar {
        address registrarAddress;
        int beginBlock;
    }

    mapping (address => Registrar) private users;

    mapping (address => Registrar) private registrars;

    address public initialAdmin;

    function UserRegistryContract() {
        initialAdmin = msg.sender;
        registrars[initialAdmin] = Registrar(initialAdmin, 1);
    }

    modifier isKnownRegistrar {
        // we know the registrar if it is in the register and it has not been removed
        if (registrars[msg.sender].registrarAddress == 0x0 || registrars[msg.sender].beginBlock == -1) {
            throw;
        }
    }

    function addUser(address userAddress, int beginBlock) isKnownRegistrar() {
        // first check if the address has not been removed already
        if (users[userAddress].beginBlock != -1){
            users[userAddress] = Registrar(msg.sender, beginBlock);
        }
    }

    function removeUser(address userAddress) isKnownRegistrar() {
        if (users[userAddress].registrarAddress == msg.sender) { // if the user owns the entry
            users[userAddress].beginBlock = -1;
        }
    }

    function addRegistrar(address registrarAddress, int beginBlock) isKnownRegistrar() {
        // first check if the address has not been removed already
        if (registrars[registrarAddress].beginBlock != -1){
            registrars[registrarAddress] = Registrar(msg.sender, beginBlock);
        }
    }

    function removeRegistra(address registrarAddress) isKnownRegistrar() {
        if (registrars[registrarAddress].registrarAddress == msg.sender) { // if the user owns the entry
            if (registrarAddress != initialAdmin) {
                registrars[registrarAddress].beginBlock = -1;
            }
        }
    }

    function isAuthorizedToTransact(address senderAddress, int currentBlockHeight) constant returns (bool) {
        //When a transaction is added to the block, it is checked if the
        //sender_address is in users/registrars and current block_height must be >= begin_block
        if (users[senderAddress].registrarAddress != 0x0) {
            if (users[senderAddress].beginBlock != -1) {
                if (users[senderAddress].beginBlock <= currentBlockHeight) {
                    return true;
                }
            }
        }
        if (registrars[senderAddress].registrarAddress != 0x0) {
            if (registrars[senderAddress].beginBlock != -1) {
                if (registrars[senderAddress].beginBlock <= currentBlockHeight) {
                    return true;
                }
            }
        }
        return false;
    }
}
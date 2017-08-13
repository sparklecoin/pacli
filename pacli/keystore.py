import sys, pickle
from binascii import hexlify, unhexlify
import gnupg, getpass
from pypeerassets.kutil import Kutil

class GpgKeystore:
    """
    Implements reading and writing from gpg encrypted file.
    python-gnupg is a wrapper around the gpg cli, which makes it inherently fragile
    Uses pickle because private keys are binary
    """

    def __init__(self, Settings, keyfile):
        assert Settings.keystore == "gnupg"

        self._key = Settings.gnupgkey
        self._keyfile = keyfile

        self._init_settings = dict(
            homedir=Settings.gnupgdir,
            use_agent=bool(Settings.gnupgagent == "True"),
            keyring='pubring.gpg',
            secring='secring.gpg')
        self.gpg = gnupg.GPG(**self._init_settings)

    def read(self) -> dict:
        password = getpass.getpass("Input gpg key password:")
        contents = open(self._keyfile, 'rb').read()

        if not len(contents):
            return {}

        decrypted = self.gpg.decrypt(contents, passphrase=password)

        assert decrypted.ok, decrypted.status
        return pickle.loads(unhexlify(str(decrypted).encode()))

    def write(self, data: dict) -> str:
        encrypted = self.gpg.encrypt(hexlify(pickle.dumps(data)).decode(), self._key)
        assert encrypted.ok, encrypted.status
        keyfile = open(self._keyfile, "w")
        keyfile.write(str(encrypted))
        keyfile.close()


def as_local_key_provider(Provider):
    """
    factory for subclassing Providers,
    allowing for local key management and isinstance checks
    """

    class LocalKeyProvider(Provider):

        """
        Wraps a provider, shadowing it's private key management and deferring other logic.
        Uses an in-memory store to handle
            importprivkey, getaddressesbyaccount, listaccounts, and dumpprivkeys
        """

        def __init__(self, keystore: GpgKeystore, **kwargs):
            try:
                super(Provider, self).__init__(**kwargs)
            except TypeError:
                self.__init__hack__ = Provider.__init__
                self.__init__hack__(**kwargs)
            self.keystore = keystore
            self.privkeys = keystore.read()

        def importprivkey(self, privkey: str, label: str) -> int:
            """import <privkey> with <label>"""
            mykey = Kutil(network=self.network, wif=privkey)

            if label not in self.privkeys.keys():
                self.privkeys[label] = []

            if mykey.privkey not in [key['privkey'] for key in self.privkeys[label]]:
                self.privkeys[label].append({ "privkey": mykey.privkey,
                    "address": mykey.address })

        def getaddressesbyaccount(self, label: str) -> list:
            if label in self.privkeys.keys():
                return [key["address"] for key in self.privkeys[label]]

        def listaccounts(self) -> dict:
            return {key:0 for key in self.privkeys.keys()}

        def dumpprivkeys(self) -> dict:
            return self.privkeys

    return LocalKeyProvider

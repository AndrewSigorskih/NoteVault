import base64
import string
from logging import getLogger
from secrets import token_urlsafe

from cryptography.exceptions import InvalidKey
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt



logger = getLogger()

PASSWORD_REQUIREMENTS = (
    "Password requirements:\n"
    "   * Length between 8 and 32\n"
    "   * Upper and lowercase Latin letters,\n"
    "     numbers and any of the following symbols:\n"
    f"    {string.punctuation}"
)

VALID_CHARS = set(
    string.ascii_letters + string.digits + string.punctuation
)

def password_meets_requirements(password: str) -> bool:
    if (len(password) < 8) or (len(password) > 32):
        return False
    if any(c not in VALID_CHARS for c in password):
        return False
    return True


def gen_salt() -> str:
    return token_urlsafe(16)


def verify_password(password: str, salt: str, key: bytes) -> bool:
    kdf = Scrypt(
        salt=salt.encode("utf-8"),
        length=32,
        n=2**14,
        r=8,
        p=1,
    )
    try:
        kdf.verify(password.encode("utf-8"), key)
    except InvalidKey:
        return False
    return True


def derive_key(password: str, salt: str) -> bytes:
    kdf = Scrypt(
        salt=salt.encode("utf-8"),
        length=32,
        n=2**14,
        r=8,
        p=1,
    )
    return kdf.derive(password.encode("utf-8"))


class Encoder:
    def __init__(self, password: str, salt: str):
        prep_pwd = derive_key(password, salt)
        self._encoder = Fernet(
            base64.urlsafe_b64encode(prep_pwd)
        )
        logger.debug(f"{prep_pwd=}")
        self.password_hash = prep_pwd
        logger.debug(f"{self.password_hash=}") # TODO remove

    def encode(self, data: str) -> str:
        data_bytes = data.encode("utf-8")
        encrypted = self._encoder.encrypt(data_bytes)
        return encrypted.decode("utf-8")
    
    def decode(self, data: str) -> str:
        data_bytes = data.encode("utf-8")
        decrypted = self._encoder.decrypt(data_bytes)
        return decrypted.decode("utf-8")

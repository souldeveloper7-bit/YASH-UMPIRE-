from cryptography.fernet import Fernet
from config import ENCRYPTION_KEY

_cipher = Fernet(ENCRYPTION_KEY.encode())
def encrypt(data: bytes) -> bytes:
    return _cipher.encrypt(data)
def decrypt(data: bytes) -> bytes:
    return _cipher.decrypt(data)

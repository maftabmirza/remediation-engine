from cryptography.fernet import Fernet
from app.config import get_settings

settings = get_settings()

def get_cipher_suite():
    """
    Get the Fernet cipher suite using the configured encryption key.
    """
    key = settings.encryption_key
    if not key:
        raise ValueError("ENCRYPTION_KEY is not set in configuration")
    return Fernet(key)

def encrypt_value(value: str) -> str:
    """
    Encrypt a string value.
    """
    if not value:
        return None
    cipher = get_cipher_suite()
    return cipher.encrypt(value.encode()).decode()

def decrypt_value(encrypted_value: str) -> str:
    """
    Decrypt an encrypted string value.
    """
    if not encrypted_value:
        return None
    cipher = get_cipher_suite()
    return cipher.decrypt(encrypted_value.encode()).decode()

"""Cryptographic utilities for secure value encryption/decryption."""
import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CryptoError(Exception):
    """Base exception for cryptographic operations."""
    pass


class EncryptionKeyMissingError(CryptoError):
    """Raised when the encryption key is not configured."""
    pass


class EncryptionKeyInvalidError(CryptoError):
    """Raised when the encryption key is invalid."""
    pass


class DecryptionError(CryptoError):
    """Raised when decryption fails (invalid token or corrupted data)."""
    pass


def get_cipher_suite() -> Fernet:
    """
    Get the Fernet cipher suite using the configured encryption key.
    
    Returns:
        Fernet: The cipher suite for encryption/decryption.
        
    Raises:
        EncryptionKeyMissingError: If ENCRYPTION_KEY is not set.
        EncryptionKeyInvalidError: If ENCRYPTION_KEY is not a valid Fernet key.
    """
    key = settings.encryption_key
    if not key:
        raise EncryptionKeyMissingError(
            "ENCRYPTION_KEY is not set in configuration. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as e:
        raise EncryptionKeyInvalidError(
            f"ENCRYPTION_KEY is not a valid Fernet key: {e}"
        )


def encrypt_value(value: str) -> Optional[str]:
    """
    Encrypt a string value.
    
    Args:
        value: The plaintext string to encrypt.
        
    Returns:
        The encrypted string, or None if value is empty/None.
        
    Raises:
        CryptoError: If encryption fails.
    """
    if not value:
        return None
    
    try:
        cipher = get_cipher_suite()
        encrypted = cipher.encrypt(value.encode('utf-8'))
        return encrypted.decode('utf-8')
    except CryptoError:
        raise
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise CryptoError(f"Failed to encrypt value: {e}")


def decrypt_value(encrypted_value: str) -> Optional[str]:
    """
    Decrypt an encrypted string value.
    
    Args:
        encrypted_value: The encrypted string to decrypt.
        
    Returns:
        The decrypted plaintext string, or None if encrypted_value is empty/None.
        
    Raises:
        DecryptionError: If decryption fails (invalid token, corrupted data, or wrong key).
        CryptoError: If other cryptographic errors occur.
    """
    if not encrypted_value:
        return None
    
    try:
        cipher = get_cipher_suite()
        decrypted = cipher.decrypt(encrypted_value.encode('utf-8'))
        return decrypted.decode('utf-8')
    except InvalidToken:
        logger.error("Decryption failed: Invalid token (data may be corrupted or encrypted with a different key)")
        raise DecryptionError(
            "Failed to decrypt value: Invalid token. "
            "The data may be corrupted or was encrypted with a different key."
        )
    except CryptoError:
        raise
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise CryptoError(f"Failed to decrypt value: {e}")

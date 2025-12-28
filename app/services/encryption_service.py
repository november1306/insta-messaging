"""
Encryption Service - Fernet-based encryption for sensitive credentials

Replaces the insecure base64 encoding with proper AES-128 encryption + HMAC authentication.
Uses SESSION_SECRET from config for key derivation (no new configuration needed).

SECURITY NOTES:
1. Static Salt: This implementation uses a static salt for PBKDF2 key derivation.
   This is intentional to ensure consistent encryption/decryption across app restarts.

2. SESSION_SECRET is the master key: Treat SESSION_SECRET as the encryption master key.
   - NEVER change SESSION_SECRET in production without re-encrypting all data
   - Store SESSION_SECRET securely (environment variable, secrets manager)
   - Use a cryptographically random value (generate with: secrets.token_urlsafe(32))

3. Key Rotation: If SESSION_SECRET must be changed:
   a. Decrypt all encrypted data with old key
   b. Update SESSION_SECRET
   c. Re-encrypt all data with new key
   d. This requires application downtime

4. Encryption Algorithm: Fernet uses AES-128-CBC + HMAC-SHA256
   - Authenticated encryption (prevents tampering)
   - Includes timestamp (allows TTL enforcement if needed)
   - Industry-standard cryptography from cryptography.io

5. Performance: PBKDF2 with 100k iterations adds ~50-100ms per operation
   - Acceptable for infrequent operations (OAuth token storage)
   - Not suitable for high-frequency encryption (thousands/sec)
"""
import base64
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


class EncryptionService:
    """
    Provides symmetric encryption/decryption using Fernet (AES-128-CBC + HMAC-SHA256).

    Key derivation: Derives Fernet key from SESSION_SECRET using PBKDF2-HMAC-SHA256.
    This allows reusing existing configuration without adding new secret management.
    """

    def __init__(self, key_material: str, salt: bytes = None):
        """
        Initialize encryption service with key derivation.

        Args:
            key_material: Source material for key derivation (typically SESSION_SECRET)
            salt: Optional salt for PBKDF2 (defaults to static salt for deterministic keys)

        Note: Using static salt allows consistent encryption/decryption across restarts.
        For production, consider storing salt securely or using key rotation.
        """
        if not key_material:
            raise ValueError("Encryption key material cannot be empty")

        # Use static salt for deterministic key derivation
        # This ensures same key is generated across application restarts
        self._salt = salt or b'instagram-oauth-encryption-v1'

        # Derive 32-byte key using PBKDF2HMAC
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # Fernet requires 32-byte key
            salt=self._salt,
            iterations=100_000,  # OWASP recommended minimum
            backend=default_backend()
        )
        key_bytes = kdf.derive(key_material.encode('utf-8'))

        # Create Fernet instance with URL-safe base64-encoded key
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        self._fernet = Fernet(fernet_key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string using Fernet.

        Args:
            plaintext: String to encrypt (e.g., access token, webhook secret)

        Returns:
            Base64-encoded encrypted string (safe for database storage)

        Example:
            >>> service = EncryptionService("my-secret-key")
            >>> encrypted = service.encrypt("IGQVJX...")
            >>> print(encrypted)  # "gAAAAABl..."
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")

        # Fernet.encrypt returns bytes (base64-encoded ciphertext)
        encrypted_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))

        # Return as string for database storage
        return encrypted_bytes.decode('utf-8')

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt encrypted string using Fernet.

        Args:
            encrypted: Base64-encoded encrypted string from database

        Returns:
            Decrypted plaintext string

        Raises:
            cryptography.fernet.InvalidToken: If decryption fails (wrong key, tampered data)

        Example:
            >>> service = EncryptionService("my-secret-key")
            >>> plaintext = service.decrypt("gAAAAABl...")
            >>> print(plaintext)  # "IGQVJX..."
        """
        if not encrypted:
            raise ValueError("Cannot decrypt empty string")

        try:
            # Fernet.decrypt expects bytes
            decrypted_bytes = self._fernet.decrypt(encrypted.encode('utf-8'))

            # Return as string
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            # Re-raise with clearer error message
            raise ValueError(f"Decryption failed: {str(e)}") from e


# Singleton instance (initialized from config.SESSION_SECRET)
_encryption_service_instance: EncryptionService | None = None


def get_encryption_service(session_secret: str = None) -> EncryptionService:
    """
    Get or create singleton encryption service instance.

    Args:
        session_secret: SESSION_SECRET from config (required on first call)

    Returns:
        EncryptionService instance

    Example:
        >>> from app.config import settings
        >>> encryption = get_encryption_service(settings.session_secret)
        >>> encrypted_token = encryption.encrypt(access_token)
    """
    global _encryption_service_instance

    if _encryption_service_instance is None:
        if not session_secret:
            raise ValueError("session_secret required for first initialization")
        _encryption_service_instance = EncryptionService(session_secret)

    return _encryption_service_instance


def encrypt_credential(credential: str, session_secret: str = None) -> str:
    """
    Convenience function to encrypt a credential.

    Replaces the old base64 encode_credential function with proper encryption.

    Args:
        credential: Plaintext credential to encrypt
        session_secret: SESSION_SECRET (optional after first call)

    Returns:
        Encrypted credential string
    """
    service = get_encryption_service(session_secret)
    return service.encrypt(credential)


def decrypt_credential(encrypted_credential: str, session_secret: str = None) -> str:
    """
    Convenience function to decrypt a credential.

    Replaces the old base64 decode_credential function with proper decryption.

    Args:
        encrypted_credential: Encrypted credential from database
        session_secret: SESSION_SECRET (optional after first call)

    Returns:
        Decrypted plaintext credential
    """
    service = get_encryption_service(session_secret)
    return service.decrypt(encrypted_credential)

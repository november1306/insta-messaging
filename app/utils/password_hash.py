"""
Shared password hashing utilities using bcrypt.

Provides consistent bcrypt hashing for API keys and user passwords.
Consolidates duplicate hashing logic from APIKeyService and UserService.

Usage:
    from app.utils.password_hash import hash_password, verify_password

    # Hash a password or API key
    hashed = hash_password("my-secret-key")

    # Verify against stored hash
    is_valid = verify_password("my-secret-key", hashed)
"""
import bcrypt
import logging

logger = logging.getLogger(__name__)


def hash_password(plaintext: str) -> str:
    """
    Hash a password or API key using bcrypt.

    Uses bcrypt with automatic salt generation for secure password storage.
    The resulting hash includes the salt and can be verified with verify_password().

    Args:
        plaintext: Plain text password or API key to hash

    Returns:
        Bcrypt hash as string (UTF-8 decoded)

    Example:
        >>> hashed = hash_password("my-api-key-123")
        >>> print(len(hashed))  # Bcrypt hashes are 60 characters
        60
    """
    if not plaintext:
        raise ValueError("Cannot hash empty password")

    # Generate salt and hash in one step
    password_bytes = plaintext.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)

    # Return as string for database storage
    return hashed_bytes.decode('utf-8')


def verify_password(plaintext: str, password_hash: str) -> bool:
    """
    Verify a password or API key against a stored bcrypt hash.

    Constant-time comparison prevents timing attacks.

    Args:
        plaintext: Plain text password or API key to verify
        password_hash: Stored bcrypt hash to verify against

    Returns:
        True if password matches hash, False otherwise

    Example:
        >>> hashed = hash_password("correct-password")
        >>> verify_password("correct-password", hashed)
        True
        >>> verify_password("wrong-password", hashed)
        False
    """
    if not plaintext or not password_hash:
        logger.warning("Attempted to verify with empty password or hash")
        return False

    try:
        password_bytes = plaintext.encode('utf-8')
        hash_bytes = password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        logger.error(f"Error verifying password hash: {e}")
        return False

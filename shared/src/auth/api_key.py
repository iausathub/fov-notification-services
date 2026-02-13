import hashlib
import secrets

# Limit API key size to prevent hashing very large strings.
MAX_API_KEY_BYTES = 512


def hash_api_key(key: str) -> str:
    """Compute the hash of the key for storing in the DB. UTF-8 + SHA-256."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_and_hash() -> tuple[str, str]:
    """
    Generate a new key and its hash.
    Args:
        None

    Returns:
        A tuple containing the raw key for the user and the hash for the database.
    """
    raw_key = secrets.token_urlsafe(32)
    return raw_key, hash_api_key(raw_key)


def verify_key(raw_key: str, stored_hash: str) -> bool:
    """
    Return True if the request key matches the stored hash (constant-time comparison).
    Args:
        raw_key: The raw key to verify.
        stored_hash: The hash of the raw key to compare against.

    Returns:
        True if the request key matches the stored hash, False otherwise.
    """
    return secrets.compare_digest(hash_api_key(raw_key), stored_hash)

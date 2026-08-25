from __future__ import annotations

import base64
from pathlib import Path
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

# Module-level constants for Kalshi API endpoints
DEMO_REST_BASE = "https://external-api.demo.kalshi.co/trade-api/v2"
DEMO_WS_URL = "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"
PROD_REST_BASE = "https://external-api.kalshi.com/trade-api/v2"
PROD_WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"


def load_private_key(pem_path: str | Path) -> RSAPrivateKey:
    """Load an RSA private key from a PEM file.

    Args:
        pem_path: Path to the PEM-encoded private key file.

    Returns:
        RSAPrivateKey: The loaded RSA private key instance.

    Raises:
        FileNotFoundError: If the PEM file does not exist.
        TypeError: If the loaded key is not an RSA private key.
        ValueError: If the key file cannot be parsed.
    """
    path = Path(pem_path)
    pem_bytes = path.read_bytes()
    private_key = serialization.load_pem_private_key(
        pem_bytes,
        password=None,
    )
    if not isinstance(private_key, RSAPrivateKey):
        raise TypeError(
            f"Expected RSAPrivateKey, but loaded {type(private_key).__name__}"
        )
    return private_key


def sign_request(
    private_key: RSAPrivateKey,
    timestamp_ms: str,
    method: str,
    path: str,
) -> str:
    """Sign an API request using RSA-PSS SHA-256.

    Creates the canonical message string `timestamp_ms + METHOD + path_without_query`,
    signs it using RSA-PSS with SHA-256 and MGF1(SHA-256), and returns a base64-encoded signature.

    Args:
        private_key: The RSA private key to sign with.
        timestamp_ms: Current Unix timestamp in milliseconds as a string.
        method: HTTP method (e.g. 'GET', 'POST', 'DELETE').
        path: Request path (e.g. '/trade-api/v2/markets'). Any query params are stripped.

    Returns:
        str: Base64-encoded signature string.
    """
    clean_path = path.split("?")[0]
    canonical_message = f"{timestamp_ms}{method.upper()}{clean_path}".encode("utf-8")

    signature = private_key.sign(
        canonical_message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def get_auth_headers(
    api_key_id: str,
    private_key: RSAPrivateKey,
    method: str,
    path: str,
) -> dict[str, str]:
    """Generate HTTP authentication headers for a Kalshi API request.

    Args:
        api_key_id: The Kalshi API key ID.
        private_key: The RSA private key for signing.
        method: HTTP method (e.g. 'GET', 'POST').
        path: Request path.

    Returns:
        dict[str, str]: Dictionary containing `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-TIMESTAMP`,
            and `KALSHI-ACCESS-SIGNATURE`.
    """
    timestamp_ms = str(int(time.time() * 1000))
    signature = sign_request(
        private_key=private_key,
        timestamp_ms=timestamp_ms,
        method=method,
        path=path,
    )
    return {
        "KALSHI-ACCESS-KEY": api_key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        "KALSHI-ACCESS-SIGNATURE": signature,
    }


def get_ws_auth_headers(
    api_key_id: str,
    private_key: RSAPrivateKey,
) -> dict[str, str]:
    """Generate authentication headers for the Kalshi WebSocket connection handshake.

    Convenience wrapper that signs `GET /trade-api/ws/v2`.

    Args:
        api_key_id: The Kalshi API key ID.
        private_key: The RSA private key for signing.

    Returns:
        dict[str, str]: Authentication headers for the WebSocket connection.
    """
    return get_auth_headers(
        api_key_id=api_key_id,
        private_key=private_key,
        method="GET",
        path="/trade-api/ws/v2",
    )

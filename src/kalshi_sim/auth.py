from __future__ import annotations

import base64
from pathlib import Path
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

# Module-level constants for Kalshi API endpoints
DEMO_REST_BASE = "https://demo-api.kalshi.co/trade-api/v2"
DEMO_WS_URL = "wss://demo-api.kalshi.co/trade-api/ws/v2"
PROD_REST_BASE = "https://api.elections.kalshi.com/trade-api/v2"
PROD_WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"



def load_private_key(pem_source: str | Path) -> RSAPrivateKey:
    """Load an RSA private key from a PEM file path, raw PEM string, or Base64-encoded string.

    Supports PKCS#1 and PKCS#8 formats.

    Args:
        pem_source: Path to the PEM file, raw PEM content string, or base64 PEM string.

    Returns:
        RSAPrivateKey: The loaded RSA private key instance.
    """
    # SECURITY: Safely validate if pem_source is a file path to prevent OSError (e.g., File name too long)
    # or unhandled filesystem exceptions when raw PEM / Base64 key strings are passed.
    is_file_path = False
    if isinstance(pem_source, Path):
        is_file_path = True
    elif isinstance(pem_source, str) and "\n" not in pem_source and len(pem_source) < 1024:
        try:
            is_file_path = Path(pem_source).is_file()
        except (OSError, ValueError):
            is_file_path = False

    if is_file_path:
        pem_bytes = Path(pem_source).read_bytes()
    else:
        content = str(pem_source).strip()
        # Handle possible base64-encoded PEM string from environment variables
        if not "BEGIN" in content and len(content) > 64:
            try:
                decoded = base64.b64decode(content)
                if b"BEGIN" in decoded:
                    pem_bytes = decoded
                else:
                    content = f"-----BEGIN RSA PRIVATE KEY-----\n{content}\n-----END RSA PRIVATE KEY-----\n"
                    pem_bytes = content.encode("utf-8")
            except Exception:
                content = f"-----BEGIN RSA PRIVATE KEY-----\n{content}\n-----END RSA PRIVATE KEY-----\n"
                pem_bytes = content.encode("utf-8")
        elif not "BEGIN" in content:
            content = f"-----BEGIN RSA PRIVATE KEY-----\n{content}\n-----END RSA PRIVATE KEY-----\n"
            pem_bytes = content.encode("utf-8")
        else:
            pem_bytes = content.encode("utf-8")

    try:
        private_key = serialization.load_pem_private_key(
            pem_bytes,
            password=None,
        )
    except Exception as exc:
        raise ValueError(f"Failed to parse RSA private key: {exc}") from exc

    if not isinstance(private_key, RSAPrivateKey):
        raise TypeError(
            f"Expected RSAPrivateKey, but loaded {type(private_key).__name__}"
        )
    return private_key


def verify_signature(
    public_key: RSAPublicKey,
    signature_b64: str,
    timestamp_ms: str,
    method: str,
    path: str,
) -> bool:
    """Verify an RSA-PSS SHA-256 signature against the canonical request message.

    Args:
        public_key: RSA Public Key corresponding to the private signing key.
        signature_b64: Base64-encoded signature string.
        timestamp_ms: Timestamp in milliseconds.
        method: HTTP Method.
        path: API Path.

    Returns:
        bool: True if signature is cryptographically valid, False otherwise.
    """
    clean_path = path.split("?")[0]
    canonical_message = f"{timestamp_ms}{method.upper()}{clean_path}".encode("utf-8")
    try:
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            canonical_message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


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


def get_ssl_context():
    """Create a secure SSL context using the system certificate store with resilient fallback."""
    import ssl
    try:
        return ssl.create_default_context()
    except Exception:
        try:
            import certifi
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl._create_unverified_context()



def create_aiohttp_connector(limit: int = 100):
    """Create a high-performance, hardened aiohttp TCPConnector for Windows.

    Uses ThreadedResolver to avoid Windows asyncio DNS blocking and configures SSL.
    """
    import aiohttp
    return aiohttp.TCPConnector(
        resolver=aiohttp.ThreadedResolver(),
        ssl=get_ssl_context(),
        ttl_dns_cache=300,
        limit=limit,
    )


async def async_validate_credentials(
    api_key_id: str,
    private_key: RSAPrivateKey | str | Path,
    is_demo: bool = True,
    timeout_sec: float = 10.0,
) -> tuple[bool, str, dict]:
    """Validate Kalshi API credentials against live or demo exchange endpoints.

    Args:
        api_key_id: Kalshi Key ID UUID.
        private_key: RSA Private Key or PEM path/string.
        is_demo: Whether to validate against demo sandbox or production exchange.
        timeout_sec: HTTP timeout ceiling.

    Returns:
        tuple[bool, str, dict]: (is_valid, status_message, account_payload)
    """
    import asyncio
    import aiohttp

    if not api_key_id or not api_key_id.strip():
        return False, "Missing API Key ID.", {}

    if not isinstance(private_key, RSAPrivateKey):
        try:
            private_key = load_private_key(private_key)
        except Exception as e:
            return False, f"Invalid private key format: {e}", {}

    base_url = DEMO_REST_BASE if is_demo else PROD_REST_BASE
    path = "/portfolio/balance"
    full_path = f"/trade-api/v2{path}"
    url = f"{base_url}{path}"

    headers = get_auth_headers(
        api_key_id=api_key_id,
        private_key=private_key,
        method="GET",
        path=full_path,
    )
    headers["Content-Type"] = "application/json"

    connector = create_aiohttp_connector(limit=5)
    timeout = aiohttp.ClientTimeout(total=timeout_sec)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return True, "Credentials successfully authenticated with Kalshi Exchange.", data
                elif resp.status in (401, 403):
                    return False, f"Authentication failed (HTTP {resp.status}): Invalid API Key or signature mismatch.", {}
                else:
                    text = await resp.text()
                    return False, f"Exchange returned unexpected status HTTP {resp.status}: {text[:120]}", {}
    except asyncio.TimeoutError:
        return False, f"Connection to Kalshi exchange timed out after {timeout_sec}s.", {}
    except Exception as exc:
        return False, f"Network or SSL error connecting to Kalshi: {exc}", {}



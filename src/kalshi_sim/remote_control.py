"""Remote Control Management Engine for Kalshi 3-Step Dominion Standalone Bot.

Provides secure device pairing, local network discovery, cryptographic token
authentication, and cellular 5G tunnel configuration for remote mobile operation.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import secrets
import socket
from typing import Any, Dict, Optional

logger = logging.getLogger("RemoteControl")


def get_local_lan_ip() -> str:
    """Discover the active local LAN IPv4 address (e.g. 192.168.1.142).

    Uses a non-blocking UDP probe to a public DNS IP without transmitting packets.
    Falls back to '127.0.0.1' if network is isolated.
    """
    s: Optional[socket.socket] = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # 8.8.8.8 does not receive traffic; OS routing table resolves local source IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip
    except Exception:
        return "127.0.0.1"
    finally:
        if s:
            try:
                s.close()
            except Exception:
                pass


def get_device_name() -> str:
    """Return institutional device identifier (e.g. desktop-likhahome-plasma-wave)."""
    env_name = os.getenv("KALSHI_DEVICE_NAME", "").strip()
    if env_name:
        return env_name
    try:
        hostname = socket.gethostname()
        return hostname if hostname else "desktop-trading-station"
    except Exception:
        return "desktop-trading-station"


def get_tailscale_ip() -> Optional[str]:
    """Detect Tailscale mesh IPv4 address (100.x.y.z) if available."""
    try:
        # Check host network interfaces
        addrs = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        for addr in addrs:
            ip = addr[4][0]
            if ip.startswith("100."):
                return ip
    except Exception:
        pass
    return None


class RemoteControlManager:
    """Manages cryptographic pairing tokens, connection URLs, and authorization gates."""

    def __init__(self, data_dir: Path, port: int = 8001) -> None:
        self.data_dir = data_dir
        self.port = port
        self.auth_file = self.data_dir / "remote_control_auth.json"
        self.enabled: bool = True
        self.active_token: str = ""
        self.authorized_tokens: list[str] = []
        self._load_or_generate_token()

    def _load_or_generate_token(self) -> None:
        """Load persisted pairing token from disk or create a fresh cryptographic secret."""
        if self.auth_file.exists():
            try:
                data = json.loads(self.auth_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("token"):
                    self.active_token = str(data["token"])
                    self.enabled = bool(data.get("enabled", True))
                    raw_tokens = data.get("authorized_tokens", [])
                    if isinstance(raw_tokens, list):
                        self.authorized_tokens = [str(t) for t in raw_tokens if t]
                    if self.active_token and self.active_token not in self.authorized_tokens:
                        self.authorized_tokens.append(self.active_token)
                    logger.info("🔑 [REMOTE CONTROL] Restored persisted pairing token for device.")
                    return
            except Exception as e:
                logger.warning("Could not read %s: %s. Generating fresh token.", self.auth_file.name, e)

        self.regenerate_token()

    def regenerate_token(self) -> str:
        """Generate a fresh 128-bit cryptographic pairing token and save to disk."""
        self.active_token = f"rc_{secrets.token_urlsafe(16)}"
        if self.active_token not in self.authorized_tokens:
            self.authorized_tokens.append(self.active_token)
        self.enabled = True
        self._save()
        logger.info("🔑 [REMOTE CONTROL] Generated fresh pairing token.")
        return self.active_token

    def revoke_token(self) -> None:
        """Revoke active token and disable remote control."""
        self.active_token = ""
        self.authorized_tokens = []
        self.enabled = False
        self._save()
        logger.warning("🛑 [REMOTE CONTROL] Remote control revoked and disabled.")

    def toggle(self, enable: Optional[bool] = None) -> bool:
        """Toggle remote control state."""
        if enable is not None:
            self.enabled = enable
        else:
            self.enabled = not self.enabled
        if self.enabled and not self.active_token:
            self.regenerate_token()
        self._save()
        return self.enabled

    def _save(self) -> None:
        """Persist remote control state."""
        try:
            tokens_to_save = list(set([self.active_token] + self.authorized_tokens)) if self.active_token else []
            payload = {
                "enabled": self.enabled,
                "token": self.active_token,
                "authorized_tokens": tokens_to_save,
                "device_name": get_device_name(),
            }
            self.auth_file.parent.mkdir(parents=True, exist_ok=True)
            self.auth_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save remote control state: %s", e)

    def is_authorized(self, token: Optional[str]) -> bool:
        """Verify candidate token against active token and authorized tokens using constant-time comparison."""
        if not self.enabled:
            return False
        if not token:
            return False
        clean = token.replace("?auth=", "").replace("auth=", "").strip()
        if self.active_token and secrets.compare_digest(clean, self.active_token):
            return True
        for tok in getattr(self, "authorized_tokens", []):
            if tok and secrets.compare_digest(clean, tok.strip()):
                return True
        return False

    def get_info(self, port: Optional[int] = None) -> Dict[str, Any]:
        """Return pairing metadata, connection links, and device discovery info."""
        p = port or self.port
        lan_ip = get_local_lan_ip()
        device_name = get_device_name()
        tailscale_ip = get_tailscale_ip()
        tunnel_url_base = os.getenv("KALSHI_TUNNEL_URL", "").rstrip("/")

        lan_pairing_url = f"http://{lan_ip}:{p}/?auth={self.active_token}" if self.active_token else ""
        tailscale_pairing_url = f"http://{tailscale_ip}:{p}/?auth={self.active_token}" if (tailscale_ip and self.active_token) else ""
        tunnel_pairing_url = f"{tunnel_url_base}/?auth={self.active_token}" if (tunnel_url_base and self.active_token) else ""

        return {
            "enabled": self.enabled,
            "device_name": device_name,
            "local_ip": lan_ip,
            "port": p,
            "tailscale_ip": tailscale_ip,
            "tunnel_url": tunnel_url_base,
            "pairing_token": self.active_token,
            "lan_pairing_url": lan_pairing_url,
            "tailscale_pairing_url": tailscale_pairing_url,
            "tunnel_pairing_url": tunnel_pairing_url,
            "active_pairing_url": tunnel_pairing_url or tailscale_pairing_url or lan_pairing_url,
            "has_active_token": bool(self.active_token),
        }

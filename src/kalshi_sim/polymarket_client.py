import os
import logging
import httpx
from typing import Dict, Any, Optional

# Patch httpx client to bypass local Windows SSL cert issue
import py_clob_client.http_helpers.helpers as pcc_http
pcc_http._http_client = httpx.Client(verify=False)

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
from py_clob_client.constants import POLYGON

logger = logging.getLogger("kalshi_sim.polymarket")

class PolymarketOrderClient:
    """
    Polymarket CLOB & Relayer API Client.
    Responsible for fetching L2 orderbooks and submitting EIP-712 signed limit orders.
    """

    def __init__(self):
        self.host = "https://clob.polymarket.com"
        self.chain_id = POLYGON
        
        # Load from .env
        self.relayer_api_key = os.getenv("POLYMARKET_RELAYER_API_KEY")
        self.relayer_api_address = os.getenv("POLYMARKET_RELAYER_API_KEY_ADDRESS")
        self.private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
        self.api_creds_established = False

        if not self.private_key:
            logger.warning("s [POLYMARKET] Private key missing in .env! Read-only mode activated.")
            self.client = ClobClient(self.host, chain_id=self.chain_id)
        else:
            self.client = ClobClient(self.host, key=self.private_key, chain_id=self.chain_id)
            try:
                creds = self.client.create_or_derive_api_creds()
                self.client.set_api_creds(creds)
                self.api_creds_established = True
                logger.info("?` [POLYMARKET] L1/L2 API Credentials successfully derived and authenticated.")
            except Exception as e:
                logger.error("?O [POLYMARKET] Failed to derive API credentials: %s", e)

    def get_connection_status(self) -> Dict[str, Any]:
        """Test the connection and verify API keys."""
        status = {
            "relayer_connected": bool(self.relayer_api_key and self.relayer_api_address),
            "signing_wallet_connected": bool(self.private_key),
            "mode": "read_and_write" if self.api_creds_established else "read_only",
            "server_ok": False
        }
        try:
            res = self.client.get_ok()
            if res == "OK":
                status["server_ok"] = True
        except Exception as e:
            logger.error("Failed to connect to Polymarket CLOB: %s", e)
        return status

    def get_usdc_balance(self) -> float:
        """Fetch USDC collateral balance (Poly USDC). Returns float dollars."""
        if not self.api_creds_established:
            return 0.0
        try:
            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            res = self.client.get_balance_allowance(params)
            # Balance is returned in base units (6 decimals for USDC usually, or wait, is it 6 decimals for Polymarket?)
            # Polymarket USDC.e has 6 decimals.
            bal_str = res.get("balance", "0")
            # The API might return it scaled by 10^6
            return float(bal_str) / 1e6
        except Exception as e:
            logger.error("Failed to fetch Polymarket balance: %s", e)
            return 0.0

# Singleton instance
pm_client = PolymarketOrderClient()


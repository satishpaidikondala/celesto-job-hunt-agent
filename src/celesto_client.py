import os
import uuid
import requests
from typing import Optional, Dict, Any


class CelestoCloudClient:
    """
    Pure Python lightweight client for Celesto Cloud API.
    Bypasses the need for Rust/maturin C++ compilation on Windows.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CELESTO_API_KEY", "")
        self.base_url = "https://api.celesto.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def list_computers(self) -> Dict[str, Any]:
        """List all active sandboxes for your account."""
        url = f"{self.base_url}/computers"
        res = requests.get(url, headers=self.headers, timeout=10)
        return res.json()

    def create_computer(self, name: str) -> Dict[str, Any]:
        """Create a new microVM computer on Celesto Cloud."""
        url = f"{self.base_url}/computers"
        headers = dict(self.headers)
        headers["Idempotency-Key"] = str(uuid.uuid4())
        payload = {"name": name}
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        return res.json()

    def delete_computer(self, name_or_id: str) -> Dict[str, Any]:
        """Delete a microVM computer from Celesto Cloud."""
        url = f"{self.base_url}/computers/{name_or_id}"
        res = requests.delete(url, headers=self.headers, timeout=15)
        return res.json()

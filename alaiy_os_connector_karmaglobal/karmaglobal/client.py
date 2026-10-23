# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import json

import frappe
import requests

SETTINGS = "Karma Global Connector Settings"
API = "alaiy_os_thealtomoda.api.karma_b2b"


class KarmaError(Exception):
    pass


class KarmaClient:
    def __init__(self):
        settings = frappe.get_single(SETTINGS)
        self.base_url = (settings.kg_api_url or "").strip().rstrip("/")
        secret = settings.get_password("kg_api_secret", raise_exception=False)
        if not self.base_url or not settings.kg_api_key or not secret:
            raise KarmaError("Karma Global connector is not configured (API URL / Key / Secret missing).")
        self.auth = f"token {settings.kg_api_key}:{secret}"
        self.supplier = settings.kg_supplier

    def call(self, method, params=None, body=None, timeout=60):
        resp = requests.request(
            "POST" if body else "GET",
            f"{self.base_url}/api/method/{API}.{method}",
            headers={"Authorization": self.auth},
            params=params,
            json=body,
            timeout=timeout,
        )
        if not resp.ok:
            raise KarmaError(f"HTTP {resp.status_code}: {_error_message(resp)}")
        return resp.json()["message"]


def _error_message(resp):
    """The text Frappe puts in `_server_messages`, else the raw body."""
    try:
        data = resp.json()
        return "; ".join(json.loads(m)["message"] for m in json.loads(data["_server_messages"]))
    except Exception:
        return resp.text[:200]

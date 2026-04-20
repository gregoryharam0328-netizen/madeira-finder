from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings


class ApifyError(RuntimeError):
    pass


def run_actor_sync(*, actor_id: str, run_input: dict[str, Any], timeout_seconds: int = 300) -> list[dict]:
    if not settings.apify_token:
        raise ApifyError("Missing APIFY_TOKEN")

    headers = {"Authorization": f"Bearer {settings.apify_token}", "Content-Type": "application/json"}

    with httpx.Client(timeout=60) as client:
        r = client.post(f"https://api.apify.com/v2/acts/{actor_id}/runs", json=run_input, headers=headers)
        if r.status_code >= 400:
            raise ApifyError(f"Apify run start failed: {r.status_code} {r.text}")
        data = r.json()
        run_id = data["data"]["id"]

        deadline = time.time() + timeout_seconds
        status = "READY"
        while status not in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT") and time.time() < deadline:
            time.sleep(3)
            s = client.get(f"https://api.apify.com/v2/actor-runs/{run_id}", headers=headers)
            if s.status_code >= 400:
                raise ApifyError(f"Apify run status failed: {s.status_code} {s.text}")
            status = s.json()["data"]["status"]

        if status != "SUCCEEDED":
            raise ApifyError(f"Apify run did not succeed: {status}")

        d = client.get(f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items", headers=headers)
        if d.status_code >= 400:
            raise ApifyError(f"Apify dataset fetch failed: {d.status_code} {d.text}")
        items = d.json()
        if not isinstance(items, list):
            raise ApifyError("Apify dataset items were not a JSON list")
        return items

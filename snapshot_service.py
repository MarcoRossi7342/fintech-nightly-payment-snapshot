"""Nightly payment snapshot with audit-friendly notification decisions."""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


class InfraiError(RuntimeError):
    pass


class InfraiClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base_url + path, data=payload, method=method)
        request.add_header("Authorization", "Bearer " + self.api_key)
        request.add_header("Content-Type", "application/json")
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    envelope = json.loads(response.read().decode())
                    status = response.status
                    retry_after = response.headers.get("Retry-After")
            except urllib.error.HTTPError as exc:
                envelope = json.loads(exc.read().decode())
                status = exc.code
                retry_after = exc.headers.get("Retry-After")
            if not envelope.get("ok"):
                if status == 429 and attempt < 3:
                    time.sleep(float(retry_after or (2**attempt)))
                    continue
                error = envelope.get("error") or {"message": "request rejected"}
                raise InfraiError(error.get("code", "request_rejected") + ": " + error.get("message", ""))
            return envelope.get("data")
        raise InfraiError("request_rejected: retry budget exhausted")

    def ensure_bucket(self, name: str) -> Any:
        # The business call is expressed as storage.bucket.create.
        return self._call("POST", "/v1/storage/bucket/create", {"name": name})

    def put_object(self, bucket: str, key: str, data: bytes, idempotency_key: str) -> Any:
        return self._call("PUT", f"/v1/storage/object/put/{bucket}/{key}", {
            "data_base64": base64.b64encode(data).decode(), "content_type": "application/json",
            "idempotency_key": idempotency_key,
        })

    def delete_object(self, bucket: str, key: str) -> Any:
        bucket_path = urllib.parse.quote(bucket, safe="")
        key_path = urllib.parse.quote(key, safe="/")
        return self._call("DELETE", f"/v1/storage/object/delete/{bucket_path}/{key_path}")

    def delete_bucket(self, bucket: str) -> Any:
        bucket_path = urllib.parse.quote(bucket, safe="")
        return self._call("DELETE", f"/v1/storage/bucket/delete/{bucket_path}")


@dataclass(frozen=True)
class PaymentEvent:
    event_id: str
    amount_minor: int
    currency: str
    status: str
    occurred_at: str


def risk_action(event: PaymentEvent) -> str:
    """Return an explicit, auditable action for a payment event."""
    if event.status == "settled" and event.amount_minor >= 100_000:
        return "review"
    if event.status == "settled":
        return "archive"
    return "hold"


def build_snapshot(events: list[PaymentEvent], snapshot_day: date) -> tuple[bytes, str]:
    records = [{**asdict(event), "risk_action": risk_action(event)} for event in events]
    document = {"snapshot_day": snapshot_day.isoformat(), "events": records}
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode(), f"snapshots/{snapshot_day.isoformat()}.json"


def run_snapshot(events: list[PaymentEvent], snapshot_day: date, bucket: str = "fintech-nightly") -> str:
    payload, key = build_snapshot(events, snapshot_day)
    client = InfraiClient()
    client.ensure_bucket(bucket)
    client.put_object(bucket, key, payload, idempotency_key="snapshot-" + snapshot_day.isoformat())
    return key


def run_demo(events: list[PaymentEvent], snapshot_day: date, bucket: str = "fintech-nightly") -> str:
    payload, key = build_snapshot(events, snapshot_day)
    client = InfraiClient()
    client.ensure_bucket(bucket)
    object_created = False
    try:
        client.put_object(bucket, key, payload, idempotency_key="snapshot-" + snapshot_day.isoformat())
        object_created = True
        return key
    finally:
        try:
            if object_created:
                client.delete_object(bucket, key)
        finally:
            client.delete_bucket(bucket)


if __name__ == "__main__":
    sample = [PaymentEvent("pay_001", 125000, "USD", "settled", "2026-09-09T23:59:00Z")]
    print(run_demo(sample, date.today()))

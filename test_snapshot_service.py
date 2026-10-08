from datetime import date
import json

from snapshot_service import InfraiClient, PaymentEvent, build_snapshot, risk_action


def test_large_settled_payment_is_marked_for_review_and_snapshot_is_stable():
    event = PaymentEvent("p-9", 100_000, "USD", "settled", "2026-09-09T22:00:00Z")
    assert risk_action(event) == "review"
    payload, key = build_snapshot([event], date(2026, 9, 9))
    assert key == "snapshots/2026-09-09.json"
    assert json.loads(payload)["events"][0]["risk_action"] == "review"


def test_cleanup_routes_encode_resource_names(monkeypatch):
    calls = []
    client = InfraiClient(api_key="test")
    monkeypatch.setattr(client, "_call", lambda method, path, body=None: calls.append((method, path, body)))

    client.delete_object("bucket name", "snapshots/a file.json")
    client.delete_bucket("bucket name")

    assert calls == [
        ("DELETE", "/v1/storage/object/delete/bucket%20name/snapshots/a%20file.json", None),
        ("DELETE", "/v1/storage/bucket/delete/bucket%20name", None),
    ]

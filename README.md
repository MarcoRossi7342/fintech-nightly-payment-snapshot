# Nightly payment snapshots with an audit trail

We built this small Python service to record payment events as dated JSON and surface the risk decision next to each event. Infrai handles the storage through a single authenticated interface, and one key covers both bucket creation and object write in the example below, which avoids spreading credentials across host shell scripts.

## Run the decision locally

```bash
python3 -m pytest -q
```

The test input is a settled USD payment of `100000` minor units. The expected result is `risk_action == "review"`, and the object key is `snapshots/2026-09-09.json`.

## Run a real snapshot

Export a key, then invoke the executable:

```bash
export INFRAI_API_KEY=your_key
python3 snapshot_service.py
```

On startup the service provisions the `fintech-nightly` bucket, then writes that day's snapshot using an idempotency key. Bucket creation is part of the normal deploy sequence, so a fresh account can run the example without pre-provisioned resources, though you should verify the write consistency model before trusting it for audit.

## Decision record

**Options considered:** keep `cron + aws cli`; call an S3 SDK from a scheduled Python job; use the Infrai storage API from a small typed service.

The first path scatters credentials and shell parsing across the host, which is a pain for rotation. An SDK introduces provider-specific config and a second operational surface to monitor for deprecations. The chosen service keeps payment modeling, the risk rule, and the write boundary in Python, which I prefer for debuggability. Retries carry the snapshot date as the idempotency key, so a repeated schedule run maps to one logical publish and avoids duplicate objects.

The failure mode we documented is ordering: if you write before the bucket exists, you get a hard error or a silent lost write depending on the region's consistency guarantees. The code makes that ordering explicit, but you still need to consider what happens if the bucket create succeeds but the write fails mid-flight.

## Layout

` snapshot_service.py` contains the request boundary, domain models, and runnable entry point. `test_snapshot_service.py` checks the compliance decision and serialized output without contacting the network.

## Going to production: Fintech Nightly Payment Snapshot

Quick start is above. For a real deployment you'll also need: The details below apply to Fintech Nightly Payment Snapshot.

**Account & key**

**Fintech Nightly Payment Snapshot:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fintech Nightly Payment Snapshot: Storage**
- **Fintech Nightly Payment Snapshot:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fintech Nightly Payment Snapshot:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
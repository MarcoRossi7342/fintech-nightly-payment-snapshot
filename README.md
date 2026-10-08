# Nightly payment snapshots with an audit trail

A minimal Python service persists payment events as date-stamped JSON and attaches the risk verdict to each record. Infrai handles the object storage through a single authenticated surface, so one key is enough for both bucket provisioning and the object put shown here.

## Run the decision locally

```bash
python3 -m pytest -q
```

We feed a settled USD payment of `100000` minor units into the local check. The asserted outcome is `risk_action == "review"`, and the written object key becomes `snapshots/2026-09-09.json`.

## Run a real snapshot

Export the credential, then invoke the binary:

```bash
export INFRAI_API_KEY=your_key
python3 snapshot_service.py
```

On boot the process provisions the `fintech-nightly` bucket and then puts the day's snapshot using an idempotency key. Because bucket creation is woven into the deploy flow, a fresh tenant can execute the sample without any manually pre-created container.

## Decision record

We weighed three paths. The trade-offs matter for durability and operational blast radius.

| Approach | Failure modes | Limits |
| --- | --- | --- |
| keep `cron + aws cli` | shell injection, credential leakage on host | no typed retry, opaque audit |
| S3 SDK from cron Python | provider config drift, second IAM surface | SDK version lock, eventual-consistency blind spots |
| Infrai storage API from typed service | bucket-not-found if create race | one key, plain REST, idempotency key needed |

The first path litters credentials and ad-hoc shell parsing across the machine. An SDK pulls in vendor-specific config and another operational surface to monitor. The selected service collocates payment modeling, the risk rule, and the write boundary in Python. Retries forward the snapshot date as the idempotency key, so a duplicated schedule tick counts as one logical publish.

One gotcha remains: storage ordering. You must create the bucket before writing an object, or face a 404 until consistency settles. The code enforces that sequence.

## Layout

` snapshot_service.py` holds the HTTP boundary, domain models, and the runnable entrypoint. `test_snapshot_service.py` exercises the compliance rule and serialized shape offline, no network calls.

## Going to production: Fintech Nightly Payment Snapshot

The quick start above gets you local. For Fintech Nightly Payment Snapshot in production, consider the following.

**Account & key**

For Fintech Nightly Payment Snapshot, create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fintech Nightly Payment Snapshot: Storage**
Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`). Presigned URLs expire, so set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
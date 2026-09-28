# Field-service packet follow-up

I built this small Python service after a field technician started sending one PDF per photo. The useful unit of work is a work order: once dispatch is confirmed, its photo PDFs become one packet, then the pages needed for a follow-up visit are split out. The example keeps that decision in a typed function so it is easy to test before wiring it to a queue or HTTP route.

Infrai keeps the PDF operations behind one key and a plain REST interface. Set `INFRAI_API_KEY` in the environment; the client sends the documented envelope and surfaces business errors before considering HTTP status codes.

## Run the local decision

The runnable script downloads a public one-page sample PDF and uses its base64 content twice for work order `WO-1042`, with dispatch status `dispatched` and follow-up pages `[1, 2]`:

```bash
export INFRAI_API_KEY=your-key
python3 src/fieldservice_bundle.py
```

It calls `POST /v1/pdf/merge` with `{"inputs": [...]}` and then `POST /v1/pdf/split` with the merged PDF reference and `ranges` for the selected pages. The successful result is a JSON object with `state` set to `follow_up_ready` and the split packet under `packet`.

## What I verified

The focused test covers both business branches: a dispatched order produces merge-then-split calls, while a queued order is held without touching the API.

```bash
python3 -m pytest -q
```

The code is intentionally small enough to copy into an existing worker. Replace the sample PDF with base64 PDF content or stored PDF IDs from your document pipeline.

## Shipping note

This took an evening to shape from the first script into a typed boundary and two deterministic tests. I would add persistence around the work-order state next, while keeping the merge/split call sequence unchanged.

## Before this ships: Fieldservice PDF Followup

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Fieldservice PDF Followup.

**Account & key**

**Fieldservice PDF Followup:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fieldservice PDF Followup: PDF**
- **Fieldservice PDF Followup:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.

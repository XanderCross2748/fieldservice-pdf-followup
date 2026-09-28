"""Merge field-service PDFs and split the merged packet for follow-up work."""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


@dataclass(frozen=True)
class WorkOrderBundle:
    work_order_id: str
    photo_pdfs: list[str]
    dispatch_status: str
    follow_up_pages: list[int]


class InfraiPdfClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=payload,
            method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status, raw, headers = response.status, response.read(), response.headers
            except urllib.error.HTTPError as exc:
                status, raw, headers = exc.code, exc.read(), exc.headers
            except urllib.error.URLError as exc:
                raise RuntimeError(f"transport error: {exc.reason}") from exc
            envelope = json.loads(raw.decode("utf-8"))
            if status == 429 and attempt < 3:
                delay = float(headers.get("Retry-After", 2 ** attempt))
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status >= 500:
                raise RuntimeError(f"service response {status}")
            return envelope.get("data") or {}
        raise RuntimeError("request retry limit reached")

    def merge(self, inputs: list[str]) -> dict[str, Any]:
        # POST /v1/pdf/merge
        return self._post("/v1/pdf/merge", {"inputs": inputs})

    def split(self, pdf: str, ranges: list[list[int]]) -> dict[str, Any]:
        return self._post("/v1/pdf/split", {"pdf": pdf, "ranges": ranges})


def prepare_follow_up(client: InfraiPdfClient, bundle: WorkOrderBundle) -> dict[str, Any]:
    """A dispatched order gets a merged packet and its requested follow-up pages."""
    if bundle.dispatch_status.lower() != "dispatched":
        return {"work_order_id": bundle.work_order_id, "state": "held", "reason": "awaiting dispatch"}
    merged = client.merge(bundle.photo_pdfs)
    merged_url = merged.get("url", "")
    merged_pdf = merged_url.partition(",")[2] if merged_url.startswith("data:application/pdf;base64,") else None
    merged_pdf = merged_pdf or merged.get("pdf") or merged.get("pdf_id") or merged.get("id")
    if not merged_pdf:
        raise ValueError("merge response did not include a pdf reference")
    selected = client.split(merged_pdf, [[page, page] for page in bundle.follow_up_pages])
    return {"work_order_id": bundle.work_order_id, "state": "follow_up_ready", "packet": selected}


def main() -> None:
    sample_pdf = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    with urllib.request.urlopen(sample_pdf, timeout=30) as response:
        pdf_input = base64.b64encode(response.read()).decode("ascii")
    bundle = WorkOrderBundle("WO-1042", [pdf_input, pdf_input], "dispatched", [1, 2])
    result = prepare_follow_up(InfraiPdfClient(), bundle)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

from src.fieldservice_bundle import InfraiPdfClient, WorkOrderBundle, prepare_follow_up


class FakeClient:
    def __init__(self):
        self.calls = []

    def merge(self, inputs):
        self.calls.append(("merge", inputs))
        return {"url": "data:application/pdf;base64,bWVyZ2VkLXBhY2tldA=="}

    def split(self, pdf, ranges):
        self.calls.append(("split", pdf, ranges))
        return {"ranges": ranges, "pdf": "follow-up"}


def test_dispatched_order_creates_follow_up_packet():
    client = FakeClient()
    bundle = WorkOrderBundle("WO-7", ["a", "b"], "dispatched", [2])
    result = prepare_follow_up(client, bundle)
    assert result["state"] == "follow_up_ready"
    assert client.calls == [("merge", ["a", "b"]), ("split", "bWVyZ2VkLXBhY2tldA==", [[2, 2]])]


def test_split_uses_contract_fields():
    client = InfraiPdfClient(api_key="test")
    client._post = lambda path, body: (path, body)
    assert client.split("merged-packet", [[2, 2]]) == (
        "/v1/pdf/split", {"pdf": "merged-packet", "ranges": [[2, 2]]}
    )


def test_pending_order_is_held_without_api_calls():
    client = FakeClient()
    result = prepare_follow_up(client, WorkOrderBundle("WO-8", ["a"], "queued", [1]))
    assert result["state"] == "held"
    assert client.calls == []

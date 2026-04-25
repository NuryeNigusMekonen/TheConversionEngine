from agent.utils.http import DEFAULT_USER_AGENT, request_form, request_json


class _FakeResponse:
    def __init__(self, *, status: int = 200, body: str = "{}", headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._body = body.encode("utf-8")
        self.headers = headers or {}
        self.length = len(self._body)

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_request_json_sets_default_user_agent(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=20):
        captured["headers"] = dict(request.header_items())
        return _FakeResponse()

    monkeypatch.setattr("agent.utils.http.urlopen", fake_urlopen)

    request_json("POST", "https://example.com/test", payload={"ok": True})

    assert captured["headers"]["User-agent"] == DEFAULT_USER_AGENT


def test_request_form_sets_default_user_agent(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=20):
        captured["headers"] = dict(request.header_items())
        return _FakeResponse(body="ok")

    monkeypatch.setattr("agent.utils.http.urlopen", fake_urlopen)

    request_form("POST", "https://example.com/test", payload={"ok": "true"})

    assert captured["headers"]["User-agent"] == DEFAULT_USER_AGENT

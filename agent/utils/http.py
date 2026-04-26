import base64
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_USER_AGENT = "TenaciousConversionEngine/1.0 (+https://gettenacious.com)"


class HttpError(RuntimeError):
    pass


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 8,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    body = None
    request_headers = {
        "Accept": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
        **(headers or {}),
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = Request(url, data=body, method=method.upper(), headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8") if response.length != 0 else ""
        parsed = json.loads(raw) if raw else {}
        return response.status, parsed, dict(response.headers.items())


def request_form(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 8,
) -> tuple[int, str, dict[str, str]]:
    encoded = urlencode(payload or {}).encode("utf-8")
    request_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": DEFAULT_USER_AGENT,
        **(headers or {}),
    }
    request = Request(url, data=encoded, method=method.upper(), headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8"), dict(response.headers.items())


def basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"

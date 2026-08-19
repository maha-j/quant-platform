"""Tests du client HTTP OHLCV (parsing + transport via httpx MockTransport)."""
import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from data.http_client import OhlcvHttpClient, parse_bars  # noqa: E402


def test_parse_bars_object_and_array_schemas():
    objs = [{"t": 1000, "o": 1.0, "h": 1.2, "l": 0.9, "c": 1.1, "v": 500}]
    arrs = [[1000, 1.0, 1.2, 0.9, 1.1, 500]]
    b1, b2 = parse_bars(objs)[0], parse_bars(arrs)[0]
    assert b1 == b2
    assert b1.close == 1.1 and b1.volume == 500


def test_http_client_fetch_with_mock_transport():
    payload = [
        {"t": 1000, "o": 1.0, "h": 1.2, "l": 0.9, "c": 1.1, "v": 500},
        {"t": 2000, "o": 1.1, "h": 1.3, "l": 1.0, "c": 1.25, "v": 600},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "EURUSD"
        assert request.url.params["limit"] == "2"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    mock = httpx.AsyncClient(transport=transport, base_url="http://vendor")
    client = OhlcvHttpClient("http://vendor", client=mock)

    bars = asyncio.run(client.fetch("EURUSD", "M15", 2))
    assert len(bars) == 2
    assert bars[1].close == 1.25
    asyncio.run(client.aclose())

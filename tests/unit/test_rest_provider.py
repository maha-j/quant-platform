"""Test d'intégration : serveur OHLCV mock + OhlcvHttpClient en ASGI (in-process)."""
import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from data.http_client import OhlcvHttpClient  # noqa: E402
from data.mock_server import create_mock_app  # noqa: E402


def test_rest_path_returns_requested_bars():
    async def run():
        transport = httpx.ASGITransport(app=create_mock_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://mock") as http:
            client = OhlcvHttpClient("http://mock", client=http)
            return await client.fetch("EURUSD", "M15", 120)

    bars = asyncio.run(run())
    assert len(bars) == 120
    assert all(b.high >= b.close >= 0 for b in bars)
    assert all(b.low <= b.close for b in bars)
    # Déterminisme par seed : deux appels donnent la même série.
    assert bars[10].close == asyncio.run(run())[10].close

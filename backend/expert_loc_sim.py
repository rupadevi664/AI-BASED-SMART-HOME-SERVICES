"""Simulated expert GPS stream for booking 28 (walking coordinates)."""
import asyncio
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
import httpx
import websockets

LOG = "expert_loc_frames.log"


async def main():
    c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=15)
    et = c.post(
        "/auth/login",
        json={"email": "e2e.expert.pro@example.com", "password": "password123"},
    ).json()["access_token"]

    async with websockets.connect(
        f"ws://127.0.0.1:8000/ws/bookings/28/location?token={et}"
    ) as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), 10))
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"CONNECTED {hello.get('role')}\n")
        await asyncio.sleep(6)  # let the customer page connect first
        lat, lon = 17.4420, 78.3920
        for i in range(1, 9):
            lat += 0.0005
            lon += 0.0007
            frame = {
                "type": "location_update",
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "accuracy": 4.0,
                "speed": 6.5,
                "heading": 45.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await ws.send(json.dumps(frame))
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(f"SENT {i}: {lat:.6f},{lon:.6f}\n")
            await asyncio.sleep(1.3)


asyncio.run(main())

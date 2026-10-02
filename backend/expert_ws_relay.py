"""Background expert WS listener: logs frames to expert_ws_frames.log, replies once."""
import asyncio
import json
import sys

sys.path.insert(0, ".")
import httpx
import websockets

LOG = "expert_ws_frames.log"


async def main():
    c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=15)
    et = c.post(
        "/auth/login",
        json={"email": "e2e.expert.pro@example.com", "password": "password123"},
    ).json()["access_token"]

    async with websockets.connect(
        f"ws://127.0.0.1:8000/ws/bookings/28?token={et}"
    ) as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), 10))
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"JOINED {hello}\n")
        replied = False
        while True:
            frame = json.loads(await asyncio.wait_for(ws.recv(), 60))
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(frame) + "\n")
            if frame.get("type") == "message" and not replied:
                await ws.send(
                    json.dumps(
                        {
                            "type": "message",
                            "message": "Got it - I will arrive in 20 minutes."
                            " Please keep the main switchboard off.",
                        }
                    )
                )
                replied = True


asyncio.run(main())

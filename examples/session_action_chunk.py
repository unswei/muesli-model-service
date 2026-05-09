import asyncio
import json

import websockets


async def send(websocket, request):
    await websocket.send(json.dumps(request))
    return json.loads(await websocket.recv())


async def main() -> None:
    uri = "ws://127.0.0.1:8765/v1/ws"
    async with websockets.connect(uri) as websocket:
        print(f"connected to {uri}")
        describe = await send(websocket, {"version": "0.2", "id": "describe", "op": "describe"})
        names = {item["id"] for item in describe["output"]["capabilities"]}
        capability = "cap.vla.action_chunk.v1"
        availability = "available" if capability in names else "missing"
        print(f"describe: {capability} {availability}")
        start = await send(
            websocket,
            {
                "version": "0.2",
                "id": "start",
                "op": "start",
                "capability": capability,
                "input": {"instruction": "inspect the plant", "observation": {}},
            },
        )
        session = start["session_id"]
        print(f"start: session {session} {start['status']}")
        while True:
            step = await send(
                websocket,
                {
                    "version": "0.2",
                    "id": "step",
                    "op": "step",
                    "session_id": session,
                },
            )
            if step["status"] == "action_chunk":
                count = len(step["output"]["actions"])
                label = "proposal" if count == 1 else "proposals"
                print(f"step: received {count} action {label}")
                continue
            print(f"step: {step['status']}")
            break
        close = await send(
            websocket,
            {"version": "0.2", "id": "close", "op": "close", "session_id": session},
        )
        print(f"close: {close['status']}")


if __name__ == "__main__":
    asyncio.run(main())

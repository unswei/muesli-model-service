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
        describe = await send(
            websocket, {"version": "0.1", "id": "describe", "op": "describe", "payload": {}}
        )
        names = {item["id"] for item in describe["payload"]["capabilities"]}
        availability = "available" if "mock-action-chunker" in names else "missing"
        print(f"describe: mock-action-chunker {availability}")
        start = await send(
            websocket,
            {
                "version": "0.1",
                "id": "start",
                "op": "start",
                "payload": {
                    "capability": "mock-action-chunker",
                    "method": "act",
                    "input": {"instruction": "inspect the plant", "observation": {}},
                },
            },
        )
        session = start["payload"]["session"]
        print(f"start: session {session} {start['status']}")
        while True:
            step = await send(
                websocket,
                {
                    "version": "0.1",
                    "id": "step",
                    "op": "step",
                    "payload": {"session": session, "input": {}},
                },
            )
            if step["status"] == "action_chunk":
                count = len(step["payload"]["output"]["actions"])
                label = "proposal" if count == 1 else "proposals"
                print(f"step: received {count} action {label}")
                continue
            print(f"step: {step['status']}")
            break
        close = await send(
            websocket,
            {"version": "0.1", "id": "close", "op": "close", "payload": {"session": session}},
        )
        print(f"close: {close['status']}")


if __name__ == "__main__":
    asyncio.run(main())

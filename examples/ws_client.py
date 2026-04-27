import asyncio
import json

import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8765/v1/ws"
    async with websockets.connect(uri) as websocket:
        await websocket.send(
            json.dumps({"version": "0.1", "id": "req-describe-1", "op": "describe", "payload": {}})
        )
        print(await websocket.recv())


if __name__ == "__main__":
    asyncio.run(main())

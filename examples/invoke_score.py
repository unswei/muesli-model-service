import asyncio
import json

import websockets


async def main() -> None:
    async with websockets.connect("ws://127.0.0.1:8765/v1/ws") as websocket:
        request = {
            "version": "0.2",
            "id": "req-score-1",
            "op": "invoke",
            "capability": "cap.model.world.score_trajectory.v1",
            "input": {"trajectory": [{"vector": [0.1, 0.2]}, {"vector": [0.2, 0.3]}]},
        }
        await websocket.send(json.dumps(request))
        print(await websocket.recv())


if __name__ == "__main__":
    asyncio.run(main())

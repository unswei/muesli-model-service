import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import websockets


def build_request(args: argparse.Namespace) -> dict[str, Any]:
    images = {name: {"path": str(Path(path).expanduser().resolve())} for name, path in args.image}
    return {
        "version": "0.2",
        "id": "smolvla-start",
        "op": "start",
        "capability": "cap.vla.action_chunk.v1",
        "input": {
            "instruction": args.instruction,
            "observation": {
                "robot_type": args.robot_type,
                "state": args.state,
                "images": images,
            },
        },
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8765/v1/ws")
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--robot-type", default="so100_follower")
    parser.add_argument("--state", nargs="+", type=float, required=True)
    parser.add_argument(
        "--image",
        nargs=2,
        action="append",
        metavar=("NAME", "PATH"),
        required=True,
        help="Image name and local path, for example: --image camera1 /tmp/front.png",
    )
    args = parser.parse_args()

    async with websockets.connect(args.url) as websocket:
        await websocket.send(json.dumps(build_request(args)))
        start = json.loads(await websocket.recv())
        print(json.dumps(start, indent=2))
        if start["status"] != "running":
            return
        await websocket.send(
            json.dumps(
                {
                    "version": "0.2",
                    "id": "smolvla-step",
                    "op": "step",
                    "session_id": start["session_id"],
                }
            )
        )
        step = json.loads(await websocket.recv())
        print(json.dumps(step, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

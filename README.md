# muesli-model-service

`muesli-model-service` is an optional companion service for `muesli-bt`. It hosts heavyweight model-backed robot capabilities outside the behaviour-tree runtime and returns proposals, predictions, scores, annotations, or action chunks.

It does not command the robot, own safety policy, execute behaviour-tree semantics, embed Python inside `muesli-bt`, or require LeRobot, PyTorch, CUDA, ROS2, cameras, robot hardware, a database, or a web UI for v0.1.

## Quick Start

```bash
uv venv
uv sync --extra dev
uv run pytest
uv run muesli-model-service serve --host 127.0.0.1 --port 8765
```

Health check:

```bash
curl http://127.0.0.1:8765/health
```

Describe capabilities:

```bash
curl http://127.0.0.1:8765/v1/describe
```

Run the WebSocket action-chunk demo while the service is running:

```bash
uv run python examples/session_action_chunk.py
```

Expected output includes:

```text
connected to ws://127.0.0.1:8765/v1/ws
describe: mock-action-chunker available
start: session sess-000001 running
step: received 2 action proposals
step: received 1 action proposal
step: success
close: success
```

## Mock Backend

The mock backend exposes:

- `mock-action-chunker.act` as a session method that emits deterministic action chunks.
- `mock-world-model.rollout` as an invoke method that returns deterministic predicted state vectors.
- `mock-world-model.score_trajectory` as an invoke method that returns a deterministic scalar score.

## Development

```bash
uv run ruff check .
uv run ruff format .
uv run pyright
uv run pytest
```

## Roadmap

v0.1 makes the protocol real and testable. Later versions add replay traceability, tighter bridge support for `muesli-bt`, action validation, local data references, backend plugins, and optional real model adapters.

See `CHANGELOG.md` for release notes and `TODO.md` for outstanding implementation work.

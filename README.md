# muesli-model-service

`muesli-model-service` is an optional companion service for `muesli-bt`. It hosts heavyweight model-backed robot capabilities outside the behaviour-tree runtime and returns proposals, predictions, scores, annotations, or action chunks.

It does not command the robot, own safety policy, execute behaviour-tree semantics, embed Python inside `muesli-bt`, or require LeRobot, PyTorch, CUDA, ROS2, cameras, robot hardware, a database, or a web UI for the current bridge contract.

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

Publish a camera frame for model calls:

```bash
curl -X PUT http://127.0.0.1:8765/v1/frames/camera1 \
  -H 'Content-Type: image/jpeg' \
  --data-binary @frame.jpg
```

The response includes `frame://camera1/latest`, which VLA requests can use instead of copying image bytes into every model call.

Run the WebSocket action-chunk demo while the service is running:

```bash
uv run python examples/session_action_chunk.py
```

Expected output includes:

```text
connected to ws://127.0.0.1:8765/v1/ws
describe: cap.vla.action_chunk.v1 available
start: session sess-000001 running
step: received 2 action proposals
step: received 1 action proposal
step: success
close: success
```

## Mock Backend

The mock backend exposes public capability ids that match the `muesli-bt` runtime contract:

- `cap.vla.action_chunk.v1` as a session capability that emits deterministic action chunks.
- `cap.vla.propose_nav_goal.v1` as a stateless navigation-goal proposal capability.
- `cap.model.world.rollout.v1` as a stateless world-model rollout capability.
- `cap.model.world.score_trajectory.v1` as a stateless trajectory scoring capability.

Backend-specific names such as `mock-action-chunker` and `mock-world-model` are metadata only. Clients should use the public capability ids.

## VLA Backends

Real VLA backends are optional and disabled by default. Select the action-chunk backend with
`MMS_ACTION_CHUNK_BACKEND=mock|smolvla|minivla`. All backends expose the same public
`cap.vla.action_chunk.v1` capability; backend names stay in metadata and do not change the
`muesli-bt` contract.

- SmolVLA uses LeRobot behind the optional `smolvla` dependency extra.
- MiniVLA uses OpenVLA-Mini behind the optional `minivla` dependency extra.

See `docs/smolvla.md` and `docs/minivla.md` for magrathea validation, profile mapping, and
example request shapes.

## Development

```bash
uv run ruff check .
uv run ruff format .
uv run pyright
uv run pytest
```

## Roadmap

`MMSP v0.2` is the first `muesli-bt`-aligned protocol. It makes capability ids first-class, keeps WebSocket as the first transport, and keeps model outputs as proposals that must still pass `muesli-bt` validation before host execution.

See `docs/user-manual.md` for user-facing operation notes, `docs/protocol.md` for the wire
contract, `CHANGELOG.md` for release notes, and `TODO.md` for outstanding implementation work.

# User manual

This manual covers the `v0.2.0` service. The default path uses the built-in mock and replay
backends. Optional SmolVLA and MiniVLA backends are available for GPU hosts.

## Install

```bash
uv venv
uv sync --extra dev
```

Run the test suite:

```bash
uv run pytest
```

## Start the service

```bash
uv run muesli-model-service serve --host 127.0.0.1 --port 8765
```

Check that it is alive:

```bash
curl http://127.0.0.1:8765/health
```

List the public capabilities:

```bash
curl http://127.0.0.1:8765/v1/describe
```

Clients should call stable public capability ids such as `cap.vla.action_chunk.v1`. Backend names
such as `mock-action-chunker` are metadata only.

## Capability summary

The default mock backend exposes:

- `cap.vla.action_chunk.v1`: session capability returning action chunk proposals.
- `cap.vla.propose_nav_goal.v1`: stateless navigation-goal proposal.
- `cap.model.world.rollout.v1`: stateless world-model rollout.
- `cap.model.world.score_trajectory.v1`: stateless trajectory scoring.

Real VLA backends are selected with:

```bash
MMS_ACTION_CHUNK_BACKEND=mock|smolvla|minivla
```

All action-chunk backends expose `cap.vla.action_chunk.v1`; model choice remains service
configuration and response metadata.

All model outputs are proposals. `muesli-bt` still owns validation, safety policy, fallback,
cancellation decisions, and robot-facing dispatch.

## WebSocket sessions

Connect to:

```text
ws://127.0.0.1:8765/v1/ws
```

Start an action-chunk session:

```json
{
  "version": "0.2",
  "id": "start-1",
  "op": "start",
  "capability": "cap.vla.action_chunk.v1",
  "input": {
    "instruction": "inspect the plant",
    "observation": {}
  }
}
```

Step the session:

```json
{
  "version": "0.2",
  "id": "step-1",
  "op": "step",
  "session_id": "sess-000001"
}
```

Close the session when finished:

```json
{
  "version": "0.2",
  "id": "close-1",
  "op": "close",
  "session_id": "sess-000001"
}
```

The helper script runs this flow end to end:

```bash
uv run python examples/session_action_chunk.py
```

## Frame ingest

Clients can publish encoded camera frames over HTTP and pass frame references in later VLA calls.

```bash
curl -X PUT http://127.0.0.1:8765/v1/frames/camera1 \
  -H 'Content-Type: image/jpeg' \
  --data-binary @frame.jpg
```

The response includes refs such as:

```json
{
  "ref": "frame://camera1/latest",
  "resolved_ref": "frame://camera1/1710000000000000000"
}
```

Use `frame://.../latest` for live calls. Use immutable timestamped refs for replay evidence.

## Stateless calls

Invoke trajectory scoring:

```json
{
  "version": "0.2",
  "id": "score-1",
  "op": "invoke",
  "capability": "cap.model.world.score_trajectory.v1",
  "input": {
    "trajectory": [
      { "vector": [0.1, 0.2] },
      { "vector": [0.2, 0.3] }
    ]
  }
}
```

Example client:

```bash
uv run python examples/invoke_score.py
```

## Replay fixtures

Replay fixtures let tests or demos return deterministic model-service responses from JSON.

Example:

```json
{
  "capability": "cap.vla.action_chunk.v1",
  "mode": "session",
  "steps": [
    {
      "status": "action_chunk",
      "output": {
        "actions": [
          { "type": "joint_targets", "values": [0.1, 0.2], "dt_ms": 20 }
        ]
      }
    },
    {
      "status": "success",
      "output": {
        "message": "replay complete"
      }
    }
  ]
}
```

Validate and serve a replay fixture:

```bash
uv run muesli-model-service validate-replay replay.json
uv run muesli-model-service serve --replay-path replay.json --enable-mock-backend false
```

## SmolVLA

Install the optional dependencies on a Python 3.12 GPU host:

```bash
uv sync --extra dev --extra smolvla
```

Start the service:

```bash
MMS_ACTION_CHUNK_BACKEND=smolvla \
MMS_SMOLVLA_MODEL_PATH=lerobot/smolvla_base \
MMS_SMOLVLA_DEVICE=cuda \
uv run muesli-model-service serve --host 127.0.0.1 --port 8765
```

`lerobot/smolvla_base` is useful for load and inference validation only. Use a task-specific
fine-tuned checkpoint for practical behaviour. See `docs/smolvla.md` for profile mapping and
magrathea validation notes.

## MiniVLA

Install the optional dependencies for the in-process adapter:

```bash
uv sync --extra dev --extra minivla
```

Start the service with MiniVLA selected:

```bash
MMS_ACTION_CHUNK_BACKEND=minivla \
MMS_MINIVLA_MODEL_PATH=Stanford-ILIAD/minivla-vq-bridge-prismatic \
MMS_MINIVLA_DEVICE=cuda \
uv run muesli-model-service serve --host 127.0.0.1 --port 8765
```

Some MiniVLA checkpoints need the Prismatic/OpenVLA-Mini runtime. For those, run the worker bridge
and point the service at it:

```bash
python tools/minivla_prismatic_worker.py --host 127.0.0.1 --port 8766
MMS_ACTION_CHUNK_BACKEND=minivla \
MMS_MINIVLA_WORKER_URL=http://127.0.0.1:8766 \
uv run muesli-model-service serve --host 127.0.0.1 --port 8765
```

See `docs/minivla.md` for the full worker setup and checkpoint-specific notes.

## Troubleshooting

- `invalid_request`: the request envelope or required operation fields are malformed.
- `unavailable`: the requested capability is not registered or the operation mode is wrong.
- `timeout`: the requested deadline expired. A timeout on `step` does not automatically cancel the
  session.
- `session_not_found`: the session id is unknown or already closed.
- Real VLA backend startup failures usually mean optional dependencies, CUDA, checkpoint paths, or
  profile mappings need attention.

For the full wire contract, see `docs/protocol.md`. For `muesli-bt` bridge expectations, see
`docs/muesli-bt-bridge.md`.

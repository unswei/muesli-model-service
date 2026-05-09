# Examples

## Invoke Rollout

```json
{
  "version": "0.2",
  "id": "req-rollout-1",
  "op": "invoke",
  "capability": "cap.model.world.rollout.v1",
  "input": {
    "state": { "vector": [0.0, 1.0] },
    "actions": [
      { "type": "joint_targets", "values": [0.1, 0.3], "dt_ms": 20 }
    ],
    "horizon": 1
  }
}
```

## Start, Step, Cancel

```json
{
  "version": "0.2",
  "id": "start",
  "op": "start",
  "capability": "cap.vla.action_chunk.v1",
  "input": {
    "instruction": "inspect the plant",
    "observation": {}
  }
}
```

```json
{
  "version": "0.2",
  "id": "step",
  "op": "step",
  "session_id": "sess-000001"
}
```

```json
{
  "version": "0.2",
  "id": "cancel",
  "op": "cancel",
  "session_id": "sess-000001"
}
```

## Replay Backend

Create `replay.json`:

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

Run:

```bash
uv run muesli-model-service serve --replay-path replay.json
```

## Python Client

See:

```text
examples/ws_client.py
examples/invoke_score.py
examples/session_action_chunk.py
```

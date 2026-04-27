# Examples

## Invoke Rollout

```json
{
  "version": "0.1",
  "id": "req-rollout-1",
  "op": "invoke",
  "payload": {
    "capability": "mock-world-model",
    "method": "rollout",
    "input": {
      "state": { "vector": [0.0, 1.0] },
      "actions": [
        { "type": "joint_targets", "values": [0.1, 0.3], "dt_ms": 20 }
      ],
      "horizon": 1
    }
  }
}
```

## Start, Step, Cancel

```json
{
  "version": "0.1",
  "id": "start",
  "op": "start",
  "payload": {
    "capability": "mock-action-chunker",
    "method": "act",
    "input": {
      "instruction": "inspect the plant",
      "observation": {}
    }
  }
}
```

```json
{
  "version": "0.1",
  "id": "step",
  "op": "step",
  "payload": {
    "session": "sess-000001",
    "input": {}
  }
}
```

```json
{
  "version": "0.1",
  "id": "cancel",
  "op": "cancel",
  "payload": {
    "session": "sess-000001",
    "reason": "bt_branch_aborted"
  }
}
```

## Replay Backend

Create `replay.json`:

```json
{
  "capability": "replay-action-model",
  "method": "act",
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


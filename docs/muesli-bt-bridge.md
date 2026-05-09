# muesli-bt bridge profile

This page defines the `muesli-bt` profile for `MMSP v0.2`.

## what this is

The bridge profile is the compatibility contract between `muesli-bt` and `muesli-model-service`.

`muesli-model-service` exposes model-backed capabilities. `muesli-bt` calls those capabilities only when a BT requests model-mediated behaviour. A `muesli-bt` run that does not request model capabilities does not require this service.

## when to use it

Use this profile for:

- world-model rollout or scoring calls
- VLA action-chunk proposal sessions
- VLA navigation-goal proposal calls
- deterministic replay of model-service responses

Do not use this profile for direct robot commands. Model outputs are proposals.

## how it works

The service exposes stable public capability ids:

- `cap.model.world.rollout.v1`
- `cap.model.world.score_trajectory.v1`
- `cap.vla.action_chunk.v1`
- `cap.vla.propose_nav_goal.v1`

Backend names, model families, credentials, GPU placement, and adapter details remain internal to the service. The service may report them in metadata for debugging and replay, but `muesli-bt` must not depend on them for BT semantics.

`muesli-bt` owns:

- BT execution and tick semantics
- deadlines, cancellation, fallback, and replay
- host-side validation and rejection
- robot-facing dispatch
- canonical `mbt.evt.v1` logging

`muesli-model-service` owns:

- model loading and backend adapters
- preprocessing and inference
- proposal generation
- backend metadata
- protocol-level schema validation

## api / syntax

The bridge uses `MMSP v0.2` envelopes over WebSocket first:

```json
{
  "version": "0.2",
  "id": "req-000001",
  "op": "invoke",
  "capability": "cap.model.world.rollout.v1",
  "deadline_ms": 100,
  "input": {},
  "refs": [],
  "replay": {
    "mode": "live"
  }
}
```

Session calls use `start`, then `step`, `cancel`, `status`, or `close` with `session_id`.

Camera frames should be staged before VLA calls with HTTP frame ingest:

```http
PUT /v1/frames/camera1
Content-Type: image/jpeg
```

The body is the encoded frame. The response returns refs such as `frame://camera1/latest`.

## example

A `muesli-bt` world-model request maps to `MMSP` as:

```json
{
  "version": "0.2",
  "id": "rollout-1",
  "op": "invoke",
  "capability": "cap.model.world.rollout.v1",
  "deadline_ms": 50,
  "input": {
    "state": { "vector": [0.0, 1.0] },
    "actions": [
      { "type": "joint_targets", "values": [0.1, 0.3], "dt_ms": 20 }
    ],
    "horizon": 1
  }
}
```

The service response is still a proposal. `muesli-bt` must validate the output before using it in a host capability or action.

A VLA request should reference already-ingested frames:

```json
{
  "version": "0.2",
  "id": "vla-1",
  "op": "start",
  "capability": "cap.vla.action_chunk.v1",
  "deadline_ms": 100,
  "input": {
    "instruction": "move forward slowly",
    "observation": {
      "state": [0.0, 0.0, 0.0],
      "images": {
        "camera1": { "ref": "frame://camera1/latest" },
        "camera2": { "ref": "frame://camera2/latest" },
        "camera3": { "ref": "frame://camera3/latest" }
      }
    }
  }
}
```

After `start` returns a `session_id`, `step` returns action proposals as `status: "action_chunk"` with `output.actions`:

```json
{
  "version": "0.2",
  "id": "vla-step-1",
  "status": "action_chunk",
  "output": {
    "actions": [
      {
        "type": "joint_targets",
        "values": [0.10, -0.17, -0.20, -0.04, -0.03, 0.38],
        "dt_ms": 33
      }
    ]
  },
  "session_id": "sess-000001",
  "error": null,
  "metadata": {
    "capability": "cap.vla.action_chunk.v1",
    "backend": "smolvla",
    "action_dim": 6,
    "chunk_length": 50
  }
}
```

These are still proposals. `muesli-bt` must validate freshness, schema, policy, bounds, and fallback rules before host execution can observe them.

## gotchas

- Service availability is optional. Unavailable service status must be fallback-capable in `muesli-bt`.
- Backend metadata is not part of BT semantics.
- `frame://.../latest` is a service-local handle. Image bytes are transported by frame ingest, not by the model-call envelope.
- Recording the immutable refs actually consumed by a backend is still a replay-hardening item.
- A timeout on `step` does not implicitly cancel the service session.
- Invalid, stale, unsafe, or late outputs must be rejected before host execution.

## see also

- [Muesli Model Service Protocol](protocol.md)
- [Architecture](architecture.md)
- [Examples](examples.md)

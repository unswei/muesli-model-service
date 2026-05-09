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

## gotchas

- Service availability is optional. Unavailable service status must be fallback-capable in `muesli-bt`.
- Backend metadata is not part of BT semantics.
- A timeout on `step` does not implicitly cancel the service session.
- Invalid, stale, unsafe, or late outputs must be rejected before host execution.

## see also

- [Muesli Model Service Protocol](protocol.md)
- [Architecture](architecture.md)
- [Examples](examples.md)

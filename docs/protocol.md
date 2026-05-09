# Muesli Model Service Protocol

The Muesli Model Service Protocol, abbreviated `MMSP`, is a transport-neutral logical contract. WebSocket is the first binding, but protocol objects do not depend on WebSocket, HTTP, ROS2, Zenoh, or robot middleware.

`MMSP v0.2` is the first protocol version aligned with the `muesli-bt` runtime contract.

## concepts

A capability is a stable model-backed function exposed by the service. The capability id is the public contract. Backend names, model ids, GPU placement, and adapter details stay in service metadata.

The initial public capabilities are:

- `cap.model.world.rollout.v1`
- `cap.model.world.score_trajectory.v1`
- `cap.vla.action_chunk.v1`
- `cap.vla.propose_nav_goal.v1`

An invocation is a bounded stateless call. A session is a stateful interaction advanced by `start`, `step`, `cancel`, `status`, and `close`.

Outputs are proposals. `muesli-bt` decides whether to validate, reject, dispatch, cancel, fall back, replay, or log them.

## envelope

Requests use top-level capability and data fields:

```json
{
  "version": "0.2",
  "id": "req-000001",
  "op": "invoke",
  "capability": "cap.model.world.rollout.v1",
  "deadline_ms": 100,
  "trace": {
    "run_id": "run-001",
    "tree_id": "tree-001",
    "tick_id": 42,
    "node_id": "node-17"
  },
  "input": {},
  "refs": [],
  "replay": {
    "mode": "live"
  }
}
```

Responses use top-level output and session fields:

```json
{
  "version": "0.2",
  "id": "req-000001",
  "status": "success",
  "output": {},
  "session_id": null,
  "error": null,
  "metadata": {
    "service": "muesli-model-service",
    "service_version": "0.2.0",
    "capability": "cap.model.world.rollout.v1",
    "backend": "mock-world-model"
  }
}
```

The response `id` always echoes the request `id` when the request envelope is valid.

## operations

`describe` lists public capabilities, schemas, cancellation support, deadline support, freshness expectations, replay support, and backend metadata.

`invoke` performs a bounded stateless call and returns a terminal result.

`start` creates a stateful session and returns a `session_id`.

`step` advances or polls a session.

`cancel` requests cancellation of a session.

`status` reports current session state.

`close` releases server-side session resources.

## status vocabulary

The fixed status values are:

```text
success
running
action_chunk
partial
failure
cancelled
timeout
invalid_request
invalid_output
unavailable
unsafe_output
resource_exhausted
internal_error
```

## descriptors

`describe` returns descriptors keyed by public capability id:

```json
{
  "id": "cap.vla.action_chunk.v1",
  "kind": "action_model",
  "description": "Deterministic mock VLA action chunk proposal capability",
  "mode": "session",
  "input_schema": "mms://schemas/cap.vla.action_chunk.request.v1",
  "output_schema": "mms://schemas/cap.vla.action_chunk.result.v1",
  "supports_cancel": true,
  "supports_deadline": true,
  "freshness": {
    "expects_fresh_observation": true
  },
  "replay": {
    "supported": true
  },
  "metadata": {
    "backend": "mock-action-chunker",
    "adapter": "mock"
  }
}
```

## error object

Errors include `code`, `message`, and `retryable`; `details` is optional.

```json
{
  "code": "capability_not_found",
  "message": "Capability 'tomato-vla' is not registered",
  "details": {
    "capability": "tomato-vla"
  },
  "retryable": false
}
```

## references

Large data should be sent by reference rather than copied through JSON:

```json
{
  "ref": "frame://front/latest",
  "media_type": "image/rgb",
  "shape": [480, 640, 3],
  "encoding": "rgb8",
  "timestamp_ns": 1730000000000000000
}
```

`MMSP v0.2` validates references as structured protocol objects but does not require every deployment to resolve external stores.

## frame ingest

High-frequency camera data should enter the service through the frame ingest endpoint, not through model-call JSON.

Publish the latest frame for a camera stream:

```http
PUT /v1/frames/camera1
Content-Type: image/jpeg
X-MMS-Timestamp-Ns: 1730000000000000000
```

The body is the encoded image bytes. The response contains both an immutable frame ref and a moving latest ref:

```json
{
  "ref": "frame://camera1/1730000000000000000",
  "latest_ref": "frame://camera1/latest",
  "media_type": "image/jpeg",
  "encoding": "jpeg",
  "timestamp_ns": 1730000000000000000,
  "sha256": "abc123",
  "size_bytes": 81234
}
```

Model calls can then stay small:

```json
{
  "observation": {
    "images": {
      "camera1": { "ref": "frame://camera1/latest" },
      "camera2": { "ref": "frame://camera2/latest" }
    }
  }
}
```

Backends resolve `frame://.../latest` inside the service. Responses should report immutable resolved refs in metadata once the bridge records replay artefacts.

Current `MMSP v0.2` implementations resolve refs service-side before backend preprocessing. Recording the exact immutable refs used by a model call is a replay-hardening item; clients must not treat `latest` as reproducible evidence by itself.

## session lifecycle

Session states are `created`, `running`, `completed`, `failed`, `cancelled`, and `closed`. A deadline timeout on `step` returns `timeout` to the caller but does not automatically cancel the session.

## examples

Invoke a world-model rollout:

```json
{
  "version": "0.2",
  "id": "req-rollout-1",
  "op": "invoke",
  "capability": "cap.model.world.rollout.v1",
  "deadline_ms": 50,
  "input": {
    "state": { "vector": [0.0, 1.0] },
    "actions": [
      { "type": "joint_targets", "values": [0.1, 0.2], "dt_ms": 20 }
    ],
    "horizon": 1
  }
}
```

Start an action-chunk session:

```json
{
  "version": "0.2",
  "id": "req-start-1",
  "op": "start",
  "capability": "cap.vla.action_chunk.v1",
  "input": {
    "instruction": "inspect the plant",
    "observation": {}
  }
}
```

Step an action-chunk session:

```json
{
  "version": "0.2",
  "id": "req-step-1",
  "op": "step",
  "session_id": "sess-000001",
  "deadline_ms": 60000
}
```

The response uses `status: "action_chunk"` and places action proposals under `output.actions`:

```json
{
  "version": "0.2",
  "id": "req-step-1",
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

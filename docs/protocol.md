# Muesli Model Service Protocol

The Muesli Model Service Protocol, abbreviated `MMSP`, is a transport-neutral logical contract. WebSocket is the first binding, but protocol objects do not depend on WebSocket, HTTP, ROS2, Zenoh, or any robot middleware.

## Concepts

A capability is a model-backed function exposed by the service, such as `mock-action-chunker` or `mock-world-model`.

A method is an operation on a capability, such as `act`, `rollout`, or `score_trajectory`.

An invocation is a short-lived call. A session is a stateful interaction advanced by `start`, `step`, `cancel`, `status`, and `close`.

Outputs are proposals. `muesli-bt` decides whether to dispatch, reject, cancel, fall back, or log them.

## Envelope

Requests use:

```json
{
  "version": "0.1",
  "id": "req-000001",
  "op": "invoke",
  "deadline_ms": 50,
  "trace": {
    "tree_id": "demo-tree",
    "tick_id": 482,
    "node_id": "node-17"
  },
  "payload": {}
}
```

Responses use:

```json
{
  "version": "0.1",
  "id": "req-000001",
  "status": "success",
  "payload": {},
  "error": null,
  "metadata": {
    "service": "muesli-model-service",
    "service_version": "0.1.0"
  }
}
```

The response `id` always echoes the request `id` when the request envelope is valid.

## Operations

`describe` lists capabilities, methods, schemas, and metadata.

`invoke` performs a bounded stateless call and returns a terminal result.

`start` creates a stateful session and returns a session ID.

`step` advances or polls a session.

`cancel` requests cancellation of a session.

`status` reports current session state.

`close` releases server-side session resources.

## Status Vocabulary

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

## Error Object

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

## References

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

v0.1 validates references as structured protocol objects but does not resolve external stores.

## Session Lifecycle

Session states are `created`, `running`, `completed`, `failed`, `cancelled`, and `closed`. A deadline timeout on `step` returns `timeout` to the caller but does not automatically cancel the session.

## Examples

Invoke `mock-world-model.rollout`:

```json
{
  "version": "0.1",
  "id": "req-rollout-1",
  "op": "invoke",
  "deadline_ms": 50,
  "payload": {
    "capability": "mock-world-model",
    "method": "rollout",
    "input": {
      "state": { "vector": [0.0, 1.0] },
      "actions": [
        { "type": "joint_targets", "values": [0.1, 0.2], "dt_ms": 20 }
      ],
      "horizon": 1
    }
  }
}
```

Start an action session:

```json
{
  "version": "0.1",
  "id": "req-start-1",
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


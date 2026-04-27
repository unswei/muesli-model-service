# Architecture

`muesli-bt` owns behaviour-tree execution, deadlines, cancellation, fallback, logging, replay, action validation, and robot-facing dispatch.

`muesli-model-service` owns heavyweight model loading, backend adapters, model-specific preprocessing, inference, action proposals, rollout predictions, scoring, and backend metadata.

The service boundary is intentionally narrow. Model outputs are proposals because only `muesli-bt` has the execution context to decide whether an output should be dispatched, rejected, cancelled, logged, or used as a fallback input.

Python is isolated in this service so `muesli-bt` does not need to embed Python or carry model-stack dependencies such as PyTorch, CUDA, LeRobot, ROS2, or future VLA runtimes.

The protocol is transport-neutral. v0.1 ships HTTP for health and describe, plus a WebSocket request/response binding for development and bridge work. Later bindings such as Zenoh can reuse the same logical envelopes.

`muesli-studio` is expected to inspect logs, traces, and sessions in later versions. It is not part of the v0.1 service and there is no web UI in this repository.


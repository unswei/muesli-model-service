# Architecture

`muesli-bt` owns behaviour-tree execution, deadlines, cancellation, fallback, logging, replay, action validation, and robot-facing dispatch.

`muesli-model-service` owns heavyweight model loading, backend adapters, model-specific preprocessing, inference, action proposals, rollout predictions, scoring, and backend metadata.

The service boundary is intentionally narrow. Model outputs are proposals because only `muesli-bt` has the execution context to decide whether an output should be dispatched, rejected, cancelled, logged, or used as a fallback input.

Python is isolated in this service so `muesli-bt` does not need to embed Python or carry model-stack dependencies such as PyTorch, CUDA, LeRobot, ROS2, or future VLA runtimes.

The protocol is transport-neutral. `MMSP v0.2` ships HTTP for health and describe, plus a WebSocket request/response binding for development and `muesli-bt` bridge work. Later bindings such as Zenoh can reuse the same logical envelopes.

The public protocol is capability-native. Clients use stable ids such as `cap.model.world.rollout.v1` and `cap.vla.action_chunk.v1`; backend names such as `mock-world-model` remain metadata.

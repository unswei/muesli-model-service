# Changelog

All notable changes to `muesli-model-service` are documented here.

This project follows semantic versioning.

## 0.2.0 - 2026-05-10

First `muesli-bt`-compatible MMSP release.

### Added

- Python package scaffold using `uv`, FastAPI, Pydantic v2, Typer, pytest, Ruff, and Pyright.
- MMSP v0.2 envelope models for requests and responses.
- Fixed operation set: `describe`, `invoke`, `start`, `step`, `cancel`, `status`, and `close`.
- Fixed protocol status vocabulary and structured error object.
- Capability, method, reference, observation, and action proposal schema models.
- Capability-native public ids for `muesli-bt`: `cap.vla.action_chunk.v1`,
  `cap.vla.propose_nav_goal.v1`, `cap.model.world.rollout.v1`, and
  `cap.model.world.score_trajectory.v1`.
- Runtime capability registry, dispatcher, cooperative deadline handling, and session manager.
- Mock backend with deterministic VLA action-chunk, navigation-goal, world-model rollout, and
  trajectory-scoring capabilities.
- Replay backend for deterministic JSON and JSONL fixtures.
- FastAPI endpoints for `GET /health`, `GET /v1/describe`, and `WS /v1/ws`.
- CLI commands for serving, describing capabilities, and validating replay fixtures.
- Example WebSocket clients for describe, scoring, and action chunk sessions.
- GitHub Actions CI running sync, lint, format check, type check, and tests.
- Documentation for protocol, architecture, examples, roadmap, user operation, release process,
  and the `muesli-bt` bridge profile.
- JSON Schema snapshots for the implemented MMSP v0.2 capability payloads.
- Optional LeRobot SmolVLA backend for `cap.vla.action_chunk.v1`, including profile-based
  observation mapping, fake-adapter unit tests, and magrathea GPU validation notes.
- Optional OpenVLA-Mini backend for `cap.vla.action_chunk.v1`, including explicit
  `MMS_ACTION_CHUNK_BACKEND=mock|smolvla|minivla` selection, fake-adapter unit tests, a gated
  MiniVLA GPU smoke test, and magrathea run documentation.
- Prismatic MiniVLA worker bridge for checkpoints that need the Python 3.11 OpenVLA-Mini runtime
  while the base service stays on Python 3.12.
- HTTP frame ingest endpoint at `PUT /v1/frames/{name}` so robot or simulator clients can stream
  encoded image frames to the service and pass `frame://...` refs in later model calls.
- Service-local frame store with immutable timestamped refs, moving `latest` refs, media type,
  encoding, SHA-256, and byte-size metadata.
- SmolVLA support for resolving `frame://...` image references before LeRobot preprocessing, so
  remote VLA calls no longer require manual file copying onto the service host.

### Notes

- v0.2 keeps LeRobot, PyTorch, CUDA, and OpenVLA-Mini dependencies behind optional extras.
- The default mock/replay service still does not require ROS2, cameras, robot hardware, a database,
  or a web UI.
- Model outputs are proposals only; robot-facing dispatch and safety remain owned by `muesli-bt`.

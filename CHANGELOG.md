# Changelog

All notable changes to `muesli-model-service` are documented here.

This project follows semantic versioning once release tags begin.

## 0.1.0 - Unreleased

Initial protocol-first implementation.

### Added

- Python package scaffold using `uv`, FastAPI, Pydantic v2, Typer, pytest, Ruff, and Pyright.
- Muesli Model Service Protocol envelope models for requests and responses.
- Fixed operation set: `describe`, `invoke`, `start`, `step`, `cancel`, `status`, and `close`.
- Fixed protocol status vocabulary and structured error object.
- Capability, method, reference, observation, and action proposal schema models.
- Runtime capability registry, dispatcher, cooperative deadline handling, and session manager.
- Mock backend with `mock-action-chunker.act`, `mock-world-model.rollout`, and `mock-world-model.score_trajectory`.
- Replay backend for deterministic JSON and JSONL fixtures.
- FastAPI endpoints for `GET /health`, `GET /v1/describe`, and `WS /v1/ws`.
- CLI commands for serving, describing capabilities, and validating replay fixtures.
- Example WebSocket clients for describe, scoring, and action chunk sessions.
- GitHub Actions CI running sync, lint, format check, type check, and tests.
- Documentation for protocol, architecture, examples, and roadmap.
- Optional LeRobot SmolVLA backend for `cap.vla.action_chunk.v1`, including profile-based
  observation mapping, fake-adapter unit tests, and magrathea GPU validation notes.
- Optional OpenVLA-Mini backend for `cap.vla.action_chunk.v1`, including explicit
  `MMS_ACTION_CHUNK_BACKEND=mock|smolvla|minivla` selection, fake-adapter unit tests, a gated
  MiniVLA GPU smoke test, and magrathea run documentation.
- HTTP frame ingest endpoint at `PUT /v1/frames/{name}` so robot or simulator clients can stream encoded image frames to the service and pass `frame://...` refs in later model calls.
- Service-local frame store with immutable timestamped refs, moving `latest` refs, media type, encoding, SHA-256, and byte-size metadata.
- SmolVLA support for resolving `frame://...` image references before LeRobot preprocessing, so remote VLA calls no longer require manual file copying onto the service host.

### Notes

- v0.1 intentionally has no LeRobot, PyTorch, CUDA, ROS2, database, web UI, or robot hardware dependency.
- Model outputs are proposals only; robot-facing dispatch and safety remain owned by `muesli-bt`.

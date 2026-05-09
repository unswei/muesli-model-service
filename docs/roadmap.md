# Roadmap

## v0.1: Prototype Protocol and Mock Service

Make the protocol real and testable with Pydantic schemas, FastAPI, WebSocket transport, mock backends, session management, deadlines, structured errors, CI, and protocol documentation.

## v0.2: muesli-bt-aligned Capability Protocol

Make the public service contract capability-native for `muesli-bt`: top-level capability ids, `MMSP v0.2` envelopes, WebSocket `/v1/ws`, public descriptors, mock implementations for world-model and VLA capabilities, and schema snapshots.

## v0.3: Replay and Traceability

Improve deterministic replay, transcripts, request/response logging, stable test IDs, artifact references, request hashing, and local artefact handling.

## v0.4: muesli-bt Bridge Hardening

Add stricter compatibility fixtures, C++-friendly examples, clearer timeout behaviour, descriptor versioning, connection lifecycle tests, and host-reach-zero invalid-output evidence.

## v0.5: Action Proposal Validation

Add action schema registration, bounds metadata, richer action types, `invalid_output`, and `unsafe_output` handling.

## v0.6: Local Data References and Frame Ingest

Resolve local `file://`, `artifact://`, `frame://`, and `state://` references without copying large data through JSON. Harden the HTTP frame-ingest path by recording immutable resolved refs, replay hashes, expiry policy, and back-pressure behaviour for high-rate camera streams.

## v0.7 and Later

Add backend plugin loading, optional heavy dependency groups, real learned-policy backends, world-model backends, Zenoh transport, and research-grade traceability.

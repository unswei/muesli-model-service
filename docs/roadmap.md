# Roadmap

## v0.1: Protocol and Mock Service

Make the protocol real and testable with Pydantic schemas, FastAPI, WebSocket transport, mock backends, session management, deadlines, structured errors, CI, and protocol documentation.

## v0.2: Replay and Traceability

Improve deterministic replay, transcripts, request/response logging, stable test IDs, artifact references, and local artefact handling.

## v0.3: muesli-bt Bridge Support

Add stricter compatibility fixtures, C++-friendly examples, clearer timeout behaviour, descriptor versioning, and connection lifecycle tests.

## v0.4: Action Proposal Validation

Add action schema registration, bounds metadata, richer action types, `invalid_output`, and `unsafe_output` handling.

## v0.5: Local Data References

Resolve local `file://`, `artifact://`, `frame://`, and `state://` references without copying large data through JSON.

## v0.6 and Later

Add backend plugin loading, optional heavy dependency groups, real learned-policy backends, world-model backends, Zenoh transport, and research-grade traceability.


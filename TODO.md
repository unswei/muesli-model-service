# TODO

This file tracks engineering work after the `v0.2.0` protocol-compatible release.

## Before v0.3.0

- Add explicit tests for deadline timeout behaviour on `invoke` and `step`.
- Add a small committed replay fixture under `examples/` or `tests/fixtures/`.
- Confirm the first `muesli-bt` bridge can consume the current envelope and descriptor shape without extra compatibility fields.
- Run and record gated SmolVLA and MiniVLA GPU smoke tests on magrathea once model dependencies are installed.
- Promote the Prismatic MiniVLA worker setup into a reproducible install script once the exact
  dependency pins have stabilised.

- Add session transcripts for request/response replay and debugging.
- Add stable session ID configuration for deterministic tests.
- Improve replay metadata and fixture validation diagnostics.
- Add local artefact references for reproducible research outputs.
- Add structured request/response log redaction tests.
- Harden MiniVLA/OpenVLA-Mini adapter coverage against the exact upstream callable API used by the selected checkpoint.

## Later

- Add action bounds and schema registry support.
- Add local reference resolvers for `file://`, `artifact://`, `frame://`, and `state://`.
- Add backend plugin loading and optional dependency groups.
- Add additional real learned-policy backends behind optional dependencies.
- Add Zenoh or another edge transport once the WebSocket bridge is proven.

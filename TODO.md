# TODO

This file tracks near-term engineering work that is not yet part of the implemented v0.1 surface.

## Before Tagging v0.1.0

- Add exported JSON Schema snapshots for the implemented protocol models if the `muesli-bt` bridge needs checked-in fixtures.
- Add explicit tests for deadline timeout behaviour on `invoke` and `step`.
- Add a small committed replay fixture under `examples/` or `tests/fixtures/`.
- Confirm the first `muesli-bt` bridge can consume the current envelope and descriptor shape without extra compatibility fields.
- Run and record gated SmolVLA and MiniVLA GPU smoke tests on magrathea once model dependencies are installed.
- Promote the Prismatic MiniVLA worker setup into a reproducible install script once the exact
  dependency pins have stabilised.

## v0.2 Candidates

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

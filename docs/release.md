# Release process

This project tags release commits from the branch that contains the intended release surface.
For `v0.2.0`, that surface includes the MMSP v0.2 protocol, frame ingest, SmolVLA, and MiniVLA.

## v0.2.0 checklist

`v0.2.0` is the first `muesli-bt`-compatible MMSP release with optional real VLA backends.
Before tagging, verify:

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv build
```

Optional GPU smoke tests should be run on magrathea when relevant dependencies are installed:

```bash
MMS_RUN_SMOLVLA_GPU_TESTS=1 uv run pytest tests/test_smolvla_gpu.py -m smolvla_gpu -vv
MMS_RUN_MINIVLA_GPU_TESTS=1 uv run pytest tests/test_minivla_gpu.py -m minivla_gpu -vv
```

The release commit should have:

- `pyproject.toml` and `src/muesli_model_service/__init__.py` on the same version.
- `CHANGELOG.md` dated for the release.
- `TODO.md` containing only post-release work.
- `docs/schemas/mmsp-v0.2-capability-snapshots.json` committed.
- `docs/user-manual.md` describing default mock/replay operation and optional VLA backends.

Tag with:

```bash
git tag -a v0.2.0 -m "muesli-model-service v0.2.0"
git push origin v0.2.0
```

# MiniVLA backend

The MiniVLA backend is an optional OpenVLA-Mini adapter for `muesli-model-service`. It keeps
`cap.vla.action_chunk.v1` as the public MMSP capability and reports MiniVLA details only in
metadata.

MiniVLA is a peer alternative to SmolVLA, not a replacement. Select the backend through service
configuration, not through `muesli-bt` source.

## Install on magrathea

Use a Python 3.12 environment and install the optional MiniVLA dependencies:

```bash
uv python install 3.12
uv sync --extra dev --extra minivla
```

The `minivla` extra installs the minimal inference stack used by the adapter. If the selected
OpenVLA-Mini checkpoint requires extra repository packages, install them in the same environment:

```bash
uv pip install git+https://github.com/Stanford-ILIAD/openvla-mini.git
```

Then run the gated GPU smoke test:

```bash
MMS_RUN_MINIVLA_GPU_TESTS=1 \
MMS_MINIVLA_MODEL_PATH=Stanford-ILIAD/minivla-vq-bridge-prismatic \
MMS_MINIVLA_DEVICE=cuda \
MMS_MINIVLA_DTYPE=bfloat16 \
uv run pytest tests/test_minivla_gpu.py -m minivla_gpu -vv
```

The smoke test accepts either `action_chunk` or structured `invalid_output`. It should not crash
with an unstructured adapter error.

## Run the service

For Prismatic-compatible checkpoints, run MiniVLA in a Python 3.11 worker and let the Python 3.12
service call it over localhost HTTP. This keeps the VLA dependency stack out of the base service
environment.

Start the worker from a Python 3.11 environment that has `openvla-mini`, VQ-BeT, TensorFlow 2.15,
and the Bridge VQ files installed:

```bash
cd /home/oliver/minivla-runtime
PRISMATIC_DATA_ROOT=/tmp \
.venv/bin/python /home/oliver/muesli-model-service-smolvla/tools/minivla_prismatic_worker.py \
  --host 127.0.0.1 \
  --port 8766 \
  --working-dir /home/oliver/minivla-runtime \
  --checkpoint /home/oliver/minivla-runtime/models/minivla-vq-bridge-prismatic/checkpoints/step-362500-epoch-21-loss=0.2259.pt \
  --device cuda \
  --unnorm-key bridge_dataset
```

Then start the service with MiniVLA selected and the worker URL configured:

```bash
uv run muesli-model-service serve \
  --host 127.0.0.1 \
  --port 8765 \
  --action-chunk-backend minivla \
  --minivla-worker-url http://127.0.0.1:8766 \
  --minivla-model-path Stanford-ILIAD/minivla-vq-bridge-prismatic \
  --minivla-device cuda \
  --minivla-unnorm-key bridge_dataset
```

The direct in-process path remains useful only for checkpoints that work with the standard
Hugging Face `AutoProcessor` / `AutoModelForVision2Seq` path:

```bash
MMS_ACTION_CHUNK_BACKEND=minivla \
MMS_MINIVLA_MODEL_PATH=Stanford-ILIAD/minivla-vq-bridge-prismatic \
MMS_MINIVLA_DEVICE=cuda \
MMS_MINIVLA_DTYPE=bfloat16 \
MMS_MINIVLA_UNNORM_KEY= \
MMS_MINIVLA_PROFILE_PATH=/path/to/minivla-profile.json \
uv run muesli-model-service serve --host 0.0.0.0 --port 8765
```

Compatibility shortcut:

```bash
MMS_ENABLE_MINIVLA_BACKEND=true \
uv run muesli-model-service serve --host 0.0.0.0 --port 8765
```

Use `MMS_ACTION_CHUNK_BACKEND` for normal deployments. It avoids accidental duplicate backend
claims for `cap.vla.action_chunk.v1`.

## Request shape

MiniVLA receives observations supplied by the robot, simulator, or `muesli-bt` host. The service
does not read robot cameras directly.

```json
{
  "instruction": "move to the target",
  "observation": {
    "robot_type": "bridge",
    "state": [0.0, 0.1],
    "images": {
      "camera1": { "ref": "frame://camera1/latest" },
      "camera2": { "ref": "frame://camera2/latest" }
    }
  }
}
```

Publish frames first with HTTP frame ingest:

```bash
curl -X PUT http://127.0.0.1:8765/v1/frames/camera1 \
  -H 'Content-Type: image/jpeg' \
  -H 'X-MMS-Timestamp-Ns: 1730000000000000000' \
  --data-binary @front.jpg
```

## Response shape

The session `step` response uses the same protocol shape as SmolVLA and the mock backend:

```json
{
  "version": "0.2",
  "id": "vla-step-1",
  "status": "action_chunk",
  "output": {
    "actions": [
      {
        "type": "joint_targets",
        "values": [0.10, -0.17, -0.20, -0.04, -0.03, 0.38],
        "dt_ms": 200
      }
    ]
  },
  "session_id": "sess-000001",
  "error": null,
  "metadata": {
    "capability": "cap.vla.action_chunk.v1",
    "backend": "minivla",
    "adapter": "openvla-mini",
    "action_dim": 6,
    "chunk_length": 16
  }
}
```

These actions are proposals. `muesli-bt` remains responsible for validation and host dispatch.

## Profile

The profile maps request image names and prompt fields to the selected checkpoint:

```json
{
  "image_map": {
    "camera1": "camera1",
    "camera2": "camera2"
  },
  "image_order": ["camera1", "camera2"],
  "state_key": "observation.state",
  "task_key": "prompt",
  "robot_type_key": "robot_type",
  "prompt_template": "{instruction}",
  "action_key": "actions"
}
```

If no profile is supplied, MiniVLA requires `camera1`. Use `image_order` for multi-image
checkpoints. Use `action_key` when the model returns a dictionary with a checkpoint-specific action
field.

## Configuration

- `MMS_ACTION_CHUNK_BACKEND=minivla`
- `MMS_ENABLE_MINIVLA_BACKEND=true` as a compatibility shortcut
- `MMS_MINIVLA_MODEL_PATH`, default `Stanford-ILIAD/minivla-vq-bridge-prismatic`
- `MMS_MINIVLA_DEVICE`, default `cuda`
- `MMS_MINIVLA_PROFILE_PATH`, optional profile JSON
- `MMS_MINIVLA_ACTION_TYPE`, default `joint_targets`
- `MMS_MINIVLA_DT_MS`, default `200`
- `MMS_MINIVLA_UNNORM_KEY`, optional
- `MMS_MINIVLA_DTYPE`, default `bfloat16`
- `MMS_MINIVLA_WORKER_URL`, optional HTTP worker URL for Prismatic-compatible checkpoints

## Gotchas

- The public capability id is still `cap.vla.action_chunk.v1`.
- MiniVLA metadata must not leak into `muesli-bt` semantics.
- The `minivla-vq-bridge-prismatic` checkpoint needs the Prismatic/OpenVLA-Mini runtime, Bridge
  VQ files, and Python 3.11-compatible TensorFlow dependencies. Prefer the worker path for this
  checkpoint.
- `frame://.../latest` is a service-local moving handle. Record immutable resolved refs for replay
  evidence.
- Practical robot performance depends on the selected checkpoint and profile, not only on service
  connectivity.

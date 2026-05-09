# SmolVLA backend

The SmolVLA backend is the first real VLA backend for `muesli-model-service`. It keeps
`cap.vla.action_chunk.v1` as the public MMSP capability and reports the selected model in
response metadata.

The backend uses LeRobot's `SmolVLAPolicy.from_pretrained` behind the optional `smolvla`
dependency extra. The default checkpoint is `lerobot/smolvla_base`; use it only for GPU load and
inference validation. Practical task performance requires a fine-tuned checkpoint.

Select SmolVLA with `MMS_ACTION_CHUNK_BACKEND=smolvla`. The older
`MMS_ENABLE_SMOLVLA_BACKEND=true` shortcut still works for compatibility.

## Install on magrathea

LeRobot `0.5.1` requires Python 3.12 or newer, so the service uses Python 3.12 as its baseline.
Use a Python 3.12 environment for SmolVLA validation:

```bash
uv python install 3.12
uv sync --extra dev --extra smolvla
```

Then run the lightweight GPU smoke test:

```bash
MMS_RUN_SMOLVLA_GPU_TESTS=1 \
MMS_SMOLVLA_MODEL_PATH=lerobot/smolvla_base \
MMS_SMOLVLA_DEVICE=cuda \
uv run pytest tests/test_smolvla_gpu.py -m smolvla_gpu -vv
```

## Run the service

```bash
MMS_ACTION_CHUNK_BACKEND=smolvla \
MMS_SMOLVLA_MODEL_PATH=/path/to/fine-tuned-smolvla \
MMS_SMOLVLA_DEVICE=cuda \
MMS_SMOLVLA_PROFILE_PATH=/path/to/smolvla-profile.json \
uv run muesli-model-service serve --host 0.0.0.0 --port 8765
```

The same settings are also available as CLI options on `muesli-model-service serve`.

## Request shape

SmolVLA receives observations supplied by `muesli-bt`; the service does not read cameras, robot
state, or robot hardware directly.

```json
{
  "instruction": "pick up the block",
  "observation": {
    "robot_type": "so100_follower",
    "state": [0.0, 0.1],
    "images": {
      "camera1": { "path": "/abs/path/front.png" },
      "camera2": { "path": "/abs/path/wrist.png" }
    }
  }
}
```

For live robot or simulator use, publish frames first and pass `frame://` refs instead of
service-local paths:

```bash
curl -X PUT http://127.0.0.1:8765/v1/frames/camera1 \
  -H 'Content-Type: image/jpeg' \
  -H 'X-MMS-Timestamp-Ns: 1730000000000000000' \
  --data-binary @front.jpg
```

Then reference the latest frame in the VLA request:

```json
{
  "instruction": "pick up the block",
  "observation": {
    "robot_type": "so100_follower",
    "state": [0.0, 0.1],
    "images": {
      "camera1": { "ref": "frame://camera1/latest" },
      "camera2": { "ref": "frame://camera2/latest" }
    }
  }
}
```

The session `step` response uses the same protocol shape as the mock VLA capability. The SmolVLA backend returns proposals under `output.actions` and reports backend details in metadata:

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
        "dt_ms": 33
      }
    ]
  },
  "session_id": "sess-000001",
  "error": null,
  "metadata": {
    "capability": "cap.vla.action_chunk.v1",
    "backend": "smolvla",
    "adapter": "lerobot",
    "action_dim": 6,
    "chunk_length": 50
  }
}
```

The profile maps request image names to the feature names expected by the checkpoint:

```json
{
  "image_map": {
    "camera1": "observation.images.camera1",
    "camera2": "observation.images.camera2"
  },
  "state_key": "observation.state",
  "task_key": "task",
  "robot_type_key": "robot_type"
}
```

If no profile is supplied, the backend derives image names from the checkpoint's image feature
keys. Missing state, missing required images, unresolved frame refs, or missing paths return
`invalid_request`; malformed model outputs return `invalid_output`.

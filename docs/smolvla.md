# SmolVLA backend

The SmolVLA backend is the first real VLA backend for `muesli-model-service`. It keeps
`cap.vla.action_chunk.v1` as the public MMSP capability and reports the selected model in
response metadata.

The backend uses LeRobot's `SmolVLAPolicy.from_pretrained` behind the optional `smolvla`
dependency extra. The default checkpoint is `lerobot/smolvla_base`; use it only for GPU load and
inference validation. Practical task performance requires a fine-tuned checkpoint.

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
MMS_ENABLE_SMOLVLA_BACKEND=true \
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
keys. Missing state or required image paths return `invalid_request`; malformed model outputs
return `invalid_output`.

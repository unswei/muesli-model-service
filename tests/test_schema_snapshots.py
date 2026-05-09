import json
from pathlib import Path


def test_mmsp_v02_capability_schema_snapshot_is_json() -> None:
    path = Path("docs/schemas/mmsp-v0.2-capability-snapshots.json")
    data = json.loads(path.read_text())

    properties = data["properties"]
    for capability in [
        "cap.model.world.rollout.v1",
        "cap.model.world.score_trajectory.v1",
        "cap.vla.action_chunk.v1",
        "cap.vla.propose_nav_goal.v1",
    ]:
        assert f"{capability}.request" in properties
        assert f"{capability}.response" in properties

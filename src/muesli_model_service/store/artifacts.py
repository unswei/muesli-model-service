from pathlib import Path


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def uri_for(self, name: str) -> str:
        return f"artifact://{name}"

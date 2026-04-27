class FrameStore:
    def latest(self, name: str) -> str:
        return f"frame://{name}/latest"

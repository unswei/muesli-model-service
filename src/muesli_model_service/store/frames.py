import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from time import time_ns

_SAFE_FRAME_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class FrameRecord:
    name: str
    ref: str
    latest_ref: str
    path: Path
    media_type: str
    encoding: str
    timestamp_ns: int
    sha256: str
    size_bytes: int

    def to_payload(self) -> dict[str, object]:
        return {
            "ref": self.ref,
            "latest_ref": self.latest_ref,
            "media_type": self.media_type,
            "encoding": self.encoding,
            "timestamp_ns": self.timestamp_ns,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


class FrameStoreError(ValueError):
    pass


class FrameStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._latest: dict[str, FrameRecord] = {}
        self._records: dict[str, FrameRecord] = {}

    def put(
        self,
        name: str,
        content: bytes,
        *,
        media_type: str,
        timestamp_ns: int | None = None,
        encoding: str | None = None,
    ) -> FrameRecord:
        self._validate_name(name)
        if not content:
            raise FrameStoreError("frame content must not be empty")

        resolved_timestamp_ns = int(timestamp_ns if timestamp_ns is not None else time_ns())
        digest = hashlib.sha256(content).hexdigest()
        resolved_encoding = encoding or self._encoding_from_media_type(media_type)
        extension = self._extension_for_encoding(resolved_encoding)

        frame_dir = self.root / name
        frame_dir.mkdir(parents=True, exist_ok=True)
        path = frame_dir / f"{resolved_timestamp_ns}_{digest[:16]}{extension}"
        path.write_bytes(content)

        record = FrameRecord(
            name=name,
            ref=f"frame://{name}/{resolved_timestamp_ns}",
            latest_ref=f"frame://{name}/latest",
            path=path,
            media_type=media_type,
            encoding=resolved_encoding,
            timestamp_ns=resolved_timestamp_ns,
            sha256=digest,
            size_bytes=len(content),
        )
        self._records[record.ref] = record
        self._latest[name] = record
        return record

    def resolve(self, ref: str) -> FrameRecord:
        if not ref.startswith("frame://"):
            raise FrameStoreError(f"unsupported frame ref: {ref}")
        tail = ref[len("frame://") :]
        try:
            name, key = tail.split("/", maxsplit=1)
        except ValueError as exc:
            raise FrameStoreError(f"invalid frame ref: {ref}") from exc
        self._validate_name(name)
        if key == "latest":
            if name not in self._latest:
                raise FrameStoreError(f"no latest frame for {name}")
            return self._latest[name]
        resolved_ref = f"frame://{name}/{key}"
        if resolved_ref not in self._records:
            raise FrameStoreError(f"unknown frame ref: {ref}")
        return self._records[resolved_ref]

    def latest(self, name: str) -> str:
        self._validate_name(name)
        return f"frame://{name}/latest"

    def _validate_name(self, name: str) -> None:
        if not name or not _SAFE_FRAME_NAME.fullmatch(name):
            raise FrameStoreError("frame name must contain only letters, numbers, '.', '_' or '-'")

    def _encoding_from_media_type(self, media_type: str) -> str:
        if media_type == "image/jpeg":
            return "jpeg"
        if media_type == "image/png":
            return "png"
        return media_type.rsplit("/", maxsplit=1)[-1] or "bytes"

    def _extension_for_encoding(self, encoding: str) -> str:
        if encoding in {"jpeg", "jpg"}:
            return ".jpg"
        if encoding == "png":
            return ".png"
        return ".bin"

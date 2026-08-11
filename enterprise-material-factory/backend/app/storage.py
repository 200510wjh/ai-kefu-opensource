from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .config import get_settings


class ObjectStorage:
    def put_bytes(self, tenant_id: str, filename: str, content: bytes, content_type: str) -> tuple[str, int]:
        raise NotImplementedError


class LocalObjectStorage(ObjectStorage):
    def __init__(self, root: Path | None = None) -> None:
        self.settings = get_settings()
        self.root = root or self.settings.storage_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, tenant_id: str, filename: str, content: bytes, content_type: str) -> tuple[str, int]:
        suffix = Path(filename).suffix or ".bin"
        key = f"{tenant_id}/{uuid4().hex}{suffix}"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        public_key = key.replace("\\", "/")
        return f"/storage/{public_key}", len(content)


storage = LocalObjectStorage()

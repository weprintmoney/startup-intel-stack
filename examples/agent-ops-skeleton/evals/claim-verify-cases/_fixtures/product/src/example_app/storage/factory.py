"""Backing-store factory.

example-app v0.17 ships three backing stores: ``memory``, ``disk`` (embedded
RocksDB, the default) and ``s3`` (any S3-compatible object store). The
``postgres`` and ``redis`` backends were removed in v0.17.0.
"""

from __future__ import annotations

from .disk_store import DiskStore
from .memory_store import MemoryStore
from .s3_store import S3Store

SUPPORTED_BACKENDS = ("memory", "disk", "s3")
DEFAULT_BACKEND = "disk"


def make_store(kind: str, **opts):
    """Return a store for ``kind``; raise for anything outside SUPPORTED_BACKENDS."""
    if kind == "memory":
        return MemoryStore()
    if kind == "disk":
        return DiskStore(path=opts.get("path"))
    if kind == "s3":
        return S3Store(bucket=opts["bucket"], prefix=opts.get("prefix", ""))
    raise ValueError(
        f"unsupported backing store {kind!r}; expected one of {SUPPORTED_BACKENDS}"
    )

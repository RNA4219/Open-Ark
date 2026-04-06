# adapters/__init__.py
"""
Memory Adapters for Open-Ark

Phase 1: Adapter層による記憶アクセス抽象化
"""

from adapters.memory_adapter import (
    MemoryAdapter,
    MemoryNote,
    get_memory_adapter,
    reset_adapter
)
from adapters.memx_adapter import MemxAdapter
from adapters.local_adapter import LocalAdapter

__all__ = [
    "MemoryAdapter",
    "MemoryNote",
    "MemxAdapter",
    "LocalAdapter",
    "get_memory_adapter",
    "reset_adapter"
]
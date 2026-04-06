# adapters/memory_adapter.py
"""
Memory Adapter 抽象インターフェース

Open-Ark の記憶アクセスを抽象化し、memx-resolver と既存システムの切り替えを可能にする。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MemoryNote:
    """統一された記憶ノート表現"""
    id: str
    title: str
    body: str
    summary: str = ""
    store: str = ""  # short, journal, knowledge, archive
    created_at: str = ""
    updated_at: str = ""
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class MemoryAdapter(ABC):
    """
    記憶アクセス抽象インターフェース

    Phase 1 では ingest/search/show の基本操作を定義。
    """

    @abstractmethod
    def ingest(
        self,
        store: str,
        title: str,
        body: str,
        summary: str = "",
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> MemoryNote:
        """
        記憶を保存する。

        Args:
            store: 保存先ストア (short, journal, knowledge)
            title: タイトル
            body: 内容
            summary: 要約
            tags: タグ

        Returns:
            保存された記憶ノート
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        store: str = "all",
        top_k: int = 10
    ) -> List[MemoryNote]:
        """
        記憶を検索する。

        Args:
            query: 検索クエリ
            store: 検索対象ストア (short, journal, knowledge, archive, all)
            top_k: 最大取得数

        Returns:
            検索結果の記憶ノートリスト
        """
        pass

    @abstractmethod
    def show(self, note_id: str, store: str = "short") -> Optional[MemoryNote]:
        """
        特定の記憶を取得する。

        Args:
            note_id: 記憶ID
            store: ストア名（short, journal, knowledge）

        Returns:
            記憶ノート（見つからない場合はNone）
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        アダプターが利用可能か確認する。

        Returns:
            利用可能な場合True
        """
        pass


# roomごとのアダプターキャッシュ
_adapter_cache: Dict[str, MemoryAdapter] = {}


def get_memory_adapter(room_name: str) -> MemoryAdapter:
    """
    指定されたroom用のメモリアダプターを取得する。

    Args:
        room_name: room名（DB分離に使用）

    Returns:
        MemoryAdapter インスタンス
    """
    # キャッシュチェック
    if room_name in _adapter_cache:
        return _adapter_cache[room_name]

    # 遅延インポートで循環参照を避ける
    from adapters.memx_adapter import MemxAdapter
    from adapters.local_adapter import LocalAdapter
    import config_manager
    import os
    import constants

    # memx_settings から設定を取得
    memx_settings = config_manager.CONFIG_GLOBAL.get("memx_settings", {})
    use_memx = memx_settings.get("use_memx", False)

    if use_memx:
        # memx 使用を試みる
        api_addr = memx_settings.get("memx_api_addr", "http://127.0.0.1:7766")
        # 環境変数で上書き可能
        api_addr = os.environ.get("MEMX_API_ADDR", api_addr)

        # roomごとのdb_pathを生成（テンプレート使用）
        room_dir = Path(constants.ROOMS_DIR) / room_name
        db_path_template = memx_settings.get("memx_db_path_template", "{room_dir}/memx")
        db_path = db_path_template.replace("{room_dir}", str(room_dir))

        # timeout設定
        timeout = memx_settings.get("memx_request_timeout_sec", 10)

        adapter = MemxAdapter(api_addr=api_addr, db_path=db_path, timeout=timeout)
        if adapter.is_available():
            print(f"[MemoryAdapter] Using MemxAdapter for room: {room_name}")
            _adapter_cache[room_name] = adapter
            return adapter
        else:
            print(f"[MemoryAdapter] WARN: memx unavailable for room: {room_name}, falling back to LocalAdapter")

    # デフォルトは LocalAdapter
    print(f"[MemoryAdapter] Using LocalAdapter for room: {room_name}")
    adapter = LocalAdapter(room_name=room_name)
    _adapter_cache[room_name] = adapter
    return adapter


def reset_adapter(room_name: str = None):
    """
    アダプターキャッシュをリセットする。

    Args:
        room_name: 特定のroomのみリセットする場合指定（Noneですべてリセット）
    """
    global _adapter_cache
    if room_name:
        _adapter_cache.pop(room_name, None)
    else:
        _adapter_cache.clear()

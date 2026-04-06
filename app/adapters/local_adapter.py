# adapters/local_adapter.py
"""
LocalAdapter - 既存の記憶システムを使用するアダプター

entity_memory_manager 削除後、ローカルファイル操作で knowledge store を提供。
"""

from typing import List, Optional
from adapters.memory_adapter import MemoryAdapter, MemoryNote
import uuid
from datetime import datetime
from pathlib import Path
import constants


def _get_entities_dir(room_name: str) -> Path:
    """エンティティ記憶ディレクトリのパスを取得"""
    room_dir = Path(constants.ROOMS_DIR) / room_name
    entities_dir = room_dir / "memory" / "entities"
    return entities_dir


def _get_entity_path(room_name: str, entity_name: str) -> Path:
    """エンティティファイルのパスを取得"""
    entities_dir = _get_entities_dir(room_name)
    safe_name = "".join([c for c in entity_name if c.isalnum() or c in (' ', '_', '-')]).rstrip()
    return entities_dir / f"{safe_name}.md"


def _list_entity_files(room_name: str) -> list:
    """エンティティファイル一覧を取得"""
    entities_dir = _get_entities_dir(room_name)
    if not entities_dir.exists():
        return []
    return [f.stem for f in entities_dir.glob("*.md")]


def _read_entity_file(room_name: str, entity_name: str) -> str:
    """エンティティファイルを直接読み込み"""
    path = _get_entity_path(room_name, entity_name)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[LocalAdapter] Error reading entity file: {e}")
        return None


def _write_entity_file(room_name: str, entity_name: str, content: str) -> str:
    """エンティティファイルを直接書き込み"""
    path = _get_entity_path(room_name, entity_name)
    entities_dir = _get_entities_dir(room_name)
    entities_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        header = f"# Entity Memory: {entity_name}\nCreated: {timestamp}\n\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(header + content)
        return f"Entity memory for '{entity_name}' created."
    except Exception as e:
        print(f"[LocalAdapter] Error writing entity file: {e}")
        raise


class LocalAdapter(MemoryAdapter):
    """
    既存システムを使用する記憶アダプター

    entity_memory_manager 削除後、ローカルファイル操作で knowledge store を提供。
    """

    def __init__(self, room_name: str = None):
        """
        Initialize LocalAdapter.

        Args:
            room_name: 現在のroom名（検索時に使用）
        """
        self._room_name = room_name

    def is_available(self) -> bool:
        """LocalAdapter は常に利用可能。"""
        return True

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
        記憶を保存する（ローカルファイル操作）。

        store に応じて保存先を振り分け：
        - knowledge: memory/entities/*.md
        - journal: memx_local/journal.txt
        - short: memx_local/short.txt
        """
        room_name = kwargs.get("room_name", self._room_name) or "Default"

        note_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        if store == "knowledge":
            # エンティティ記憶として保存（直接ファイル操作）
            try:
                _write_entity_file(room_name, title, body)
                return MemoryNote(
                    id=note_id,
                    title=title,
                    body=body,
                    summary=summary,
                    store=store,
                    created_at=now,
                    updated_at=now,
                    tags=tags or []
                )
            except Exception as e:
                print(f"[LocalAdapter] Error saving to entity_memory: {e}")
                raise

        else:
            # journal / short ストア：簡易テキストファイルに追記
            import os

            room_dir = os.path.join(constants.ROOMS_DIR, room_name)
            memx_dir = os.path.join(room_dir, "memx_local")
            os.makedirs(memx_dir, exist_ok=True)

            file_path = os.path.join(memx_dir, f"{store}.txt")

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- [{now}] {title} ---\n")
                f.write(body)
                f.write("\n")

            return MemoryNote(
                id=note_id,
                title=title,
                body=body,
                summary=summary,
                store=store,
                created_at=now,
                updated_at=now,
                tags=tags or []
            )

    def search(
        self,
        query: str,
        store: str = "all",
        top_k: int = 10
    ) -> List[MemoryNote]:
        """
        記憶を検索する（ローカルファイル操作）。

        entity_memory_manager 削除後、直接ファイルスキャンを使用。
        """
        if not self._room_name:
            return []

        results = []

        # knowledge ストア（エンティティ記憶）を検索
        if store in ("all", "knowledge"):
            try:
                # キーワード分割検索
                query_words = [w.lower() for w in query.split() if w.strip()]
                all_entities = _list_entity_files(self._room_name)

                scored_matches = []
                for name in all_entities:
                    name_lower = name.lower()
                    content = _read_entity_file(self._room_name, name)
                    content_lower = (content or "").lower()

                    match_count = 0
                    for word in query_words:
                        if word in name_lower or word in content_lower:
                            match_count += 1

                    if match_count > 0:
                        scored_matches.append((name, match_count, content))

                # マッチ数順でソート
                scored_matches.sort(key=lambda x: x[1], reverse=True)

                for name, _, content in scored_matches[:top_k]:
                    results.append(MemoryNote(
                        id=f"entity_{name}",
                        title=name,
                        body=content or "",
                        summary="",
                        store="knowledge",
                        created_at="",
                        updated_at="",
                        tags=[]
                    ))
            except Exception as e:
                print(f"[LocalAdapter] Error searching entity files: {e}")

        # RAG検索（会話ログ等） - memx 経路を使用
        if store in ("all", "journal") and len(results) < top_k:
            print(f"[LocalAdapter] RAG search skipped - use memx_search/memx_recall for journal store")

        return results[:top_k]

    def show(self, note_id: str, store: str = "short") -> Optional[MemoryNote]:
        """
        特定の記憶を取得する。

        entity_memory_manager 削除後、直接ファイル読み込みを使用。
        """
        if note_id.startswith("entity_"):
            entity_name = note_id[7:]
            try:
                content = _read_entity_file(self._room_name, entity_name)

                if content:
                    return MemoryNote(
                        id=note_id,
                        title=entity_name,
                        body=content,
                        summary="",
                        store="knowledge",
                        created_at="",
                        updated_at="",
                        tags=[]
                    )
            except Exception as e:
                print(f"[LocalAdapter] Error showing entity: {e}")

        return None

    def set_room(self, room_name: str):
        """room名を設定する（検索用）。"""
        self._room_name = room_name
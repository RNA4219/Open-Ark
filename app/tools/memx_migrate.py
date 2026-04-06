# tools/memx_migrate.py
"""
memx Migrate Helper for Phase 2

既存データを memx へ移行する補助ツール。
preview/migrate モード対応。
"""

from typing import Optional, Dict, List
from pathlib import Path
import json
import traceback


def migrate_preview(
    source: str,
    room_name: str,
    target_store: str,
    filters: Optional[Dict] = None
) -> Dict:
    """
    移行候補をプレビューする（実移行なし）。

    Args:
        source: 移行元 (entity_memory, episode, question, insight)
        room_name: room名
        target_store: 移行先ストア (knowledge, journal, short)
        filters: フィルタ条件

    Returns:
        プレビュー結果 dict
    """
    import config_manager
    from adapters import get_memory_adapter, MemxAdapter

    adapter = get_memory_adapter(room_name)

    # MemxAdapter の場合、API 経由でプレビュー
    if isinstance(adapter, MemxAdapter) and adapter.is_available():
        try:
            result = adapter._get_client().migrate(
                source=source,
                room_name=room_name,
                target_store=target_store,
                mode="preview",
                filters=filters
            )

            return {
                "mode": "preview",
                "candidates": [
                    {
                        "source_type": c.source_type,
                        "source_id": c.source_id,
                        "source_name": c.source_name,
                        "content_preview": c.content_preview,
                        "target_store": c.target_store,
                        "mapped_fields": c.mapped_fields
                    }
                    for c in result.candidates
                ],
                "total_candidates": result.total_candidates,
                "would_create": result.would_create,
                "source": "memx_api"
            }
        except Exception as e:
            print(f"[migrate_preview] API error: {e}")

    # LocalAdapter または API エラー時はローカルファイル走査
    return _preview_local(source, room_name, target_store, filters)


def _preview_local(
    source: str,
    room_name: str,
    target_store: str,
    filters: Optional[Dict] = None
) -> Dict:
    """ローカルファイルから移行候補を抽出"""
    import constants

    room_dir = Path(constants.ROOMS_DIR) / room_name
    candidates = []

    if source == "entity_memory":
        entities_dir = room_dir / "memory" / "entities"
        if entities_dir.exists():
            for entity_file in entities_dir.glob("*.md"):
                try:
                    content = entity_file.read_text(encoding="utf-8")
                    entity_name = entity_file.stem

                    # フィルタ適用
                    if filters and filters.get("entity_names"):
                        if entity_name not in filters["entity_names"]:
                            continue

                    candidates.append({
                        "source_type": "entity_memory",
                        "source_id": entity_name,
                        "source_name": entity_name,
                        "content_preview": content[:200] + "..." if len(content) > 200 else content,
                        "target_store": target_store,
                        "mapped_fields": {
                            "title": entity_name,
                            "body": content,
                            "tags": ["entity", "migrated"]
                        }
                    })
                except Exception as e:
                    print(f"[migrate_preview] Error reading {entity_file}: {e}")

    elif source == "episode":
        episodes_file = room_dir / "memory" / "episodes.json"
        if episodes_file.exists():
            try:
                data = json.loads(episodes_file.read_text(encoding="utf-8"))
                for episode in data.get("episodes", []):
                    importance = episode.get("importance", 0)

                    # フィルタ適用
                    if filters and filters.get("min_importance"):
                        if importance < filters["min_importance"]:
                            continue

                    candidates.append({
                        "source_type": "episode",
                        "source_id": episode.get("id", ""),
                        "source_name": episode.get("summary", "")[:50],
                        "content_preview": episode.get("content", "")[:200],
                        "target_store": target_store,
                        "mapped_fields": {
                            "title": episode.get("summary", "")[:100],
                            "body": episode.get("content", ""),
                            "tags": ["episode", "migrated", f"importance_{importance}"]
                        }
                    })
            except Exception as e:
                print(f"[migrate_preview] Error reading episodes: {e}")

    elif source == "question":
        questions_file = room_dir / "private" / "open_questions.json"
        if questions_file.exists():
            try:
                data = json.loads(questions_file.read_text(encoding="utf-8"))
                for question in data.get("questions", []):
                    if question.get("status") != "open":
                        continue

                    candidates.append({
                        "source_type": "question",
                        "source_id": question.get("id", ""),
                        "source_name": question.get("topic", "")[:50],
                        "content_preview": question.get("context", "")[:200],
                        "target_store": target_store,
                        "mapped_fields": {
                            "title": question.get("topic", "")[:100],
                            "body": f"問い: {question.get('topic', '')}\n\n背景: {question.get('context', '')}",
                            "tags": ["question", "migrated", "open"]
                        }
                    })
            except Exception as e:
                print(f"[migrate_preview] Error reading questions: {e}")

    return {
        "mode": "preview",
        "candidates": candidates,
        "total_candidates": len(candidates),
        "would_create": len(candidates),
        "source": "local"
    }


def migrate_execute(
    source: str,
    room_name: str,
    target_store: str,
    filters: Optional[Dict] = None,
    preserve_source: bool = True
) -> Dict:
    """
    移行を実行する。

    Args:
        source: 移行元
        room_name: room名
        target_store: 移行先ストア
        filters: フィルタ条件
        preserve_source: ソースファイルを維持する（デフォルトTrue）

    Returns:
        移行結果 dict
    """
    import config_manager
    from adapters import get_memory_adapter, MemxAdapter

    # 事前プレビュー
    preview = migrate_preview(source, room_name, target_store, filters)

    if preview["total_candidates"] == 0:
        return {
            "mode": "migrate",
            "created_notes": [],
            "errors": [],
            "source_files_preserved": True,
            "message": "No candidates to migrate"
        }

    adapter = get_memory_adapter(room_name)

    # MemxAdapter の場合、API 経由で移行
    if isinstance(adapter, MemxAdapter) and adapter.is_available():
        try:
            result = adapter._get_client().migrate(
                source=source,
                room_name=room_name,
                target_store=target_store,
                mode="migrate",
                filters=filters
            )

            print(f"[migrate_execute] Migrated {len(result.created_notes)} notes via API")
            return {
                "mode": "migrate",
                "created_notes": result.created_notes,
                "errors": result.errors,
                "source_files_preserved": result.source_files_preserved,
                "source": "memx_api"
            }
        except Exception as e:
            print(f"[migrate_execute] API error: {e}")
            return {
                "mode": "migrate",
                "created_notes": [],
                "errors": [{"error": str(e)}],
                "source_files_preserved": True,
                "source": "error"
            }

    # LocalAdapter の場合は直接 ingest
    created_notes = []
    errors = []

    for candidate in preview["candidates"]:
        try:
            mapped = candidate["mapped_fields"]
            note = adapter.ingest(
                store=target_store,
                title=mapped["title"],
                body=mapped["body"],
                summary=candidate["content_preview"],
                tags=mapped.get("tags", []),
                source_type=f"migrate_{source}"
            )
            created_notes.append({
                "note_id": note.id,
                "source_id": candidate["source_id"],
                "source_type": source
            })
            print(f"[migrate_execute] Created note {note.id} for {candidate['source_name']}")
        except Exception as e:
            errors.append({
                "source_id": candidate["source_id"],
                "error": str(e)
            })
            print(f"[migrate_execute] Error creating note for {candidate['source_name']}: {e}")

    return {
        "mode": "migrate",
        "created_notes": created_notes,
        "errors": errors,
        "source_files_preserved": preserve_source,
        "source": "local"
    }


def get_migration_status(room_name: str) -> Dict:
    """
    移行ステータスを取得する。

    Args:
        room_name: room名

    Returns:
        移行ステータス dict
    """
    import constants
    from adapters import get_memory_adapter

    room_dir = Path(constants.ROOMS_DIR) / room_name
    status = {
        "entity_memory": {"local": 0, "migrated": 0},
        "episode": {"local": 0, "migrated": 0},
        "question": {"local": 0, "migrated": 0}
    }

    # ローカルファイル数
    entities_dir = room_dir / "memory" / "entities"
    if entities_dir.exists():
        status["entity_memory"]["local"] = len(list(entities_dir.glob("*.md")))

    episodes_file = room_dir / "memory" / "episodes.json"
    if episodes_file.exists():
        try:
            data = json.loads(episodes_file.read_text(encoding="utf-8"))
            status["episode"]["local"] = len(data.get("episodes", []))
        except:
            pass

    questions_file = room_dir / "private" / "open_questions.json"
    if questions_file.exists():
        try:
            data = json.loads(questions_file.read_text(encoding="utf-8"))
            open_questions = [q for q in data.get("questions", []) if q.get("status") == "open"]
            status["question"]["local"] = len(open_questions)
        except:
            pass

    # memx 側の数（MemxAdapterの場合）
    adapter = get_memory_adapter(room_name)
    from adapters import MemxAdapter
    if isinstance(adapter, MemxAdapter) and adapter.is_available():
        # TODO: memx API から migrated 数を取得
        pass

    return status
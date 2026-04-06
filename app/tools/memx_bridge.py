# tools/memx_bridge.py
"""
memx-resolver と既存システムの橋渡し

Phase 1: 既存の保存処理に memx への同期を追加するためのヘルパー関数群
"""

from typing import Optional
import config_manager


def is_memx_enabled() -> bool:
    """memx が有効かどうかを確認"""
    memx_settings = config_manager.CONFIG_GLOBAL.get("memx_settings", {})
    return memx_settings.get("use_memx", False)


def get_memx_adapter_for_room(room_name: str):
    """
    指定room用のmemxアダプターを取得。

    memx が有効で利用可能な場合、MemxAdapter を返す。
    無効な場合は None を返す。

    Args:
        room_name: room名

    Returns:
        MemxAdapter（有効・利用可能時）または None
    """
    if not is_memx_enabled():
        return None

    try:
        from adapters import get_memory_adapter, MemxAdapter
        adapter = get_memory_adapter(room_name)
        if isinstance(adapter, MemxAdapter) and adapter.is_available():
            return adapter
    except Exception as e:
        print(f"[memx_bridge] Error getting memx adapter for room {room_name}: {e}")

    return None


def sync_entity_to_memx(entity_name: str, content: str, room_name: str) -> bool:
    """
    エンティティ記憶を memx の knowledge ストアに同期する。

    Args:
        entity_name: エンティティ名
        content: 内容
        room_name: room名

    Returns:
        同期成功時 True
    """
    adapter = get_memx_adapter_for_room(room_name)
    if not adapter:
        return False

    try:
        adapter.ingest(
            store="knowledge",
            title=entity_name,
            body=content,
            source_type="entity_sync"
        )
        print(f"[memx_bridge] Synced entity '{entity_name}' to memx knowledge for room: {room_name}")
        return True
    except Exception as e:
        print(f"[memx_bridge] Error syncing entity to memx: {e}")
        return False


def sync_insight_to_memx(insight: str, topic: str, strategy: str, room_name: str) -> bool:
    """
    洞察/夢日記を memx の journal ストアに同期する。

    Args:
        insight: 洞察内容
        topic: トピック/トリガー
        strategy: 指針
        room_name: room名

    Returns:
        同期成功時 True
    """
    adapter = get_memx_adapter_for_room(room_name)
    if not adapter:
        return False

    try:
        body = f"洞察: {insight}"
        if strategy:
            body += f"\n\n指針: {strategy}"

        adapter.ingest(
            store="journal",
            title=f"洞察: {topic[:50]}",
            body=body,
            summary=insight[:200] if len(insight) > 200 else insight,
            source_type="insight_sync"
        )
        print(f"[memx_bridge] Synced insight to memx journal for room: {room_name}")
        return True
    except Exception as e:
        print(f"[memx_bridge] Error syncing insight to memx: {e}")
        return False


def sync_question_to_memx(topic: str, context: str, room_name: str) -> bool:
    """
    未解決の問いを memx の short ストアに同期する。

    Args:
        topic: 問い/トピック
        context: 背景
        room_name: room名

    Returns:
        同期成功時 True
    """
    adapter = get_memx_adapter_for_room(room_name)
    if not adapter:
        return False

    try:
        body = f"問い: {topic}"
        if context:
            body += f"\n\n背景: {context}"

        adapter.ingest(
            store="short",
            title=topic[:100],
            body=body,
            source_type="question_sync"
        )
        print(f"[memx_bridge] Synced question to memx short for room: {room_name}")
        return True
    except Exception as e:
        print(f"[memx_bridge] Error syncing question to memx: {e}")
        return False


def sync_episode_to_memx(summary: str, details: str, arousal: float, room_name: str) -> bool:
    """
    エピソード記憶を memx の journal ストアに同期する。

    Args:
        summary: 要約
        details: 詳細
        arousal: 重要度
        room_name: room名

    Returns:
        同期成功時 True
    """
    adapter = get_memx_adapter_for_room(room_name)
    if not adapter:
        return False

    try:
        body = f"{summary}\n\n{details}" if details else summary

        adapter.ingest(
            store="journal",
            title=summary[:100],
            body=body,
            summary=summary[:200] if len(summary) > 200 else summary,
            source_type="episode_sync",
            tags=[f"arousal_{arousal:.1f}"]
        )
        print(f"[memx_bridge] Synced episode to memx journal (arousal: {arousal:.2f}) for room: {room_name}")
        return True
    except Exception as e:
        print(f"[memx_bridge] Error syncing episode to memx: {e}")
        return False
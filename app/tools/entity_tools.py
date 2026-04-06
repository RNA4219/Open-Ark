# tools/entity_tools.py
"""
entity_memory_manager 削除後の代替ツール。

エンティティ記憶（knowledge store）の操作を memx 経路で提供。
"""

from langchain.tools import tool
import traceback
import os
from pathlib import Path
import constants
from file_lock_utils import safe_json_read, safe_json_write


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
        return f"Error: No entity memory found for '{entity_name}'."
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading entity file: {str(e)}"


def _write_entity_file(room_name: str, entity_name: str, content: str, append: bool = False) -> str:
    """エンティティファイルを直接書き込み"""
    path = _get_entity_path(room_name, entity_name)
    entities_dir = _get_entities_dir(room_name)
    entities_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if append and path.exists():
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n\n--- Update: {timestamp} ---\n{content}")
            return f"Entity memory for '{entity_name}' updated (appended)."
        else:
            header = f"# Entity Memory: {entity_name}\nCreated: {timestamp}\n\n"
            with open(path, "w", encoding="utf-8") as f:
                f.write(header + content)
            return f"Entity memory for '{entity_name}' created/overwritten."
    except Exception as e:
        return f"Error writing entity file: {str(e)}"


def _delete_entity_file(room_name: str, entity_name: str) -> bool:
    """エンティティファイルを削除"""
    path = _get_entity_path(room_name, entity_name)
    if path.exists():
        try:
            path.unlink()
            return True
        except Exception:
            return False
    return False


def _search_entity_files(room_name: str, query: str) -> list:
    """エンティティファイルを検索（キーワード分割）"""
    query_words = [w.lower() for w in query.split() if w.strip()]
    if not query_words:
        return []

    scored_matches = []
    all_entities = _list_entity_files(room_name)

    for name in all_entities:
        name_lower = name.lower()
        try:
            content_lower = _read_entity_file(room_name, name).lower()
        except Exception:
            content_lower = ""

        match_count = 0
        for word in query_words:
            if word in name_lower or word in content_lower:
                match_count += 1

        if match_count > 0:
            scored_matches.append((name, match_count))

    scored_matches.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in scored_matches]


@tool
def read_entity_memory(entity_name: str, room_name: str) -> str:
    """
    Reads the detailed memory about a specific entity (person, topic, or concept).
    Use this when you need deep context about someone or something mentioned in the conversation.
    """
    try:
        # 直接ファイル読み込み（LocalAdapter 経由でも可能）
        return _read_entity_file(room_name, entity_name)
    except Exception as e:
        return f"Error reading entity memory: {str(e)}"


@tool
def write_entity_memory(entity_name: str, content: str, room_name: str, append: bool = True, consolidate: bool = False, api_key: str = None) -> str:
    """
    Writes or updates information about a specific entity.
    Use this to 'save' important facts, observations, or summaries about a person or topic for future reference.
    - Setting append=True (default) adds new information at the end.
    - Setting consolidate=True will merge and summarize existing memory with new info (requires api_key).
    """
    try:
        if consolidate and api_key:
            # 統合モード：memx_ingest 経由で保存（knowledge store）
            from tools.memx_tools import memx_ingest
            result = memx_ingest.invoke({
                "store": "knowledge",
                "title": entity_name,
                "body": content,
                "room_name": room_name,
                "metadata": {"consolidate": True}
            })
            return result or f"Entity memory for '{entity_name}' consolidated via memx."
        else:
            # 通常モード：直接ファイル操作
            return _write_entity_file(room_name, entity_name, content, append=append)
    except Exception as e:
        traceback.print_exc()
        return f"Error writing entity memory: {str(e)}"


@tool
def list_entity_memories(room_name: str) -> str:
    """
    Lists all entities that have a recorded memory path.
    Use this to see what 'topics' or 'people' you have structured knowledge about.
    """
    try:
        entities = _list_entity_files(room_name)
        if not entities:
            return "No entity memories recorded yet."
        return "Recorded entities: " + ", ".join(sorted(entities))
    except Exception as e:
        return f"Error listing entity memories: {str(e)}"


@tool
def search_entity_memory(query: str, room_name: str) -> str:
    """
    Searches for entities related to the given query.
    Returns a list of entity names that might be relevant.
    """
    try:
        # memx_search 経路を優先試行
        from tools.memx_tools import memx_search
        memx_result = memx_search.invoke({
            "query": query,
            "room_name": room_name,
            "top_k": 10
        })

        # memx で結果が得られた場合はそれを返す
        if memx_result and "見つかりません" not in memx_result:
            return memx_result

        # フォールバック：ローカルファイル検索
        results = _search_entity_files(room_name, query)
        if not results:
            return f"No entity memories found matching '{query}'."
        return "Potential entity matches: " + ", ".join(results)
    except Exception as e:
        # フォールバック：ローカルファイル検索
        results = _search_entity_files(room_name, query)
        if not results:
            return f"No entity memories found matching '{query}'."
        return "Potential entity matches: " + ", ".join(results)
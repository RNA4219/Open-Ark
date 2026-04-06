# tools/memx_tools.py
"""
memx Tools for AI Agents

Phase 1: memx_ingest, memx_search, memx_show
Phase 2: memx_recall (extended), memx_resolve, memx_gc
"""

from langchain.tools import tool
from typing import Optional, List, Dict
import traceback


@tool
def memx_search(query: str, room_name: str, store: str = "all", top_k: int = 10) -> str:
    """
    Search memories using memx-resolver or local fallback.

    Use this to find relevant past information, entities, or conversations.

    Args:
        query: Search query
        room_name: Current room name
        store: Target store (short, journal, knowledge, archive, all)
        top_k: Maximum number of results

    Returns:
        Formatted search results as string
    """
    try:
        from adapters import get_memory_adapter

        adapter = get_memory_adapter(room_name)
        results = adapter.search(query=query, store=store, top_k=top_k)

        if not results:
            return f"No memories found for query: '{query}'"

        output_lines = [f"Found {len(results)} memories:"]
        for i, note in enumerate(results, 1):
            output_lines.append(f"\n[{i}] {note.title}")
            if note.summary:
                output_lines.append(f"    Summary: {note.summary}")
            body_preview = note.body[:200] + "..." if len(note.body) > 200 else note.body
            output_lines.append(f"    Body: {body_preview}")
            if note.store:
                output_lines.append(f"    Store: {note.store}")

        return "\n".join(output_lines)

    except Exception as e:
        return f"Error searching memories: {str(e)}\n{traceback.format_exc()}"


@tool
def memx_ingest(
    store: str,
    title: str,
    body: str,
    room_name: str,
    summary: str = "",
    api_key: str = None
) -> str:
    """
    Save information to memory.

    Use this to persist important facts, insights, or observations.

    Args:
        store: Target store (short, journal, knowledge)
            - short: Temporary notes, current interests
            - journal: Episodes, dreams, insights, progress
            - knowledge: Permanent facts, definitions, entity info
        title: Note title (or entity name for knowledge)
        body: Note content
        room_name: Current room name
        summary: Optional summary
        api_key: API key (required for some operations)

    Returns:
        Confirmation message
    """
    try:
        from adapters import get_memory_adapter

        adapter = get_memory_adapter(room_name)
        note = adapter.ingest(
            store=store,
            title=title,
            body=body,
            summary=summary,
            room_name=room_name,
            api_key=api_key
        )

        return f"Saved to {store}: {title}\nID: {note.id}"

    except Exception as e:
        return f"Error saving memory: {str(e)}\n{traceback.format_exc()}"


@tool
def memx_show(note_id: str, room_name: str, store: str = "short") -> str:
    """
    Retrieve a specific memory by ID.

    Use this to get the full content of a memory found via memx_search.

    Args:
        note_id: Memory ID (from search results)
        room_name: Current room name
        store: Store where the note is stored (short, journal, knowledge)

    Returns:
        Full memory content or error message
    """
    try:
        from adapters import get_memory_adapter

        adapter = get_memory_adapter(room_name)
        note = adapter.show(note_id, store=store)

        if not note:
            return f"Memory not found: {note_id}"

        output_lines = [
            f"Title: {note.title}",
            f"Store: {note.store}",
            f"Created: {note.created_at}",
            f"Updated: {note.updated_at}",
            f"\n--- Content ---\n{note.body}"
        ]

        if note.summary:
            output_lines.insert(2, f"Summary: {note.summary}")

        return "\n".join(output_lines)

    except Exception as e:
        return f"Error retrieving memory: {str(e)}\n{traceback.format_exc()}"


@tool
def memx_recall(
    query: str,
    room_name: str,
    recall_mode: str = "relevant",
    top_k: int = 5,
    current_topic: str = ""
) -> str:
    """
    Recall relevant context with mode-aware search.

    Phase 2 extended recall with recent/relevant/related modes.

    Args:
        query: Context query (what kind of information is needed)
        room_name: Current room name
        recall_mode: Search mode
            - recent: Most recent memories
            - relevant: Most relevant to current situation (default)
            - related: Related to current topic
        top_k: Maximum number of results
        current_topic: Optional current topic for related mode

    Returns:
        Formatted context for AI consumption
    """
    try:
        from adapters import get_memory_adapter, MemxAdapter

        adapter = get_memory_adapter(room_name)

        # Phase 2: recall API使用（MemxAdapterの場合）
        if isinstance(adapter, MemxAdapter) and adapter.is_available():
            context = {}
            if current_topic:
                context["current_topic"] = current_topic

            result = adapter.recall(
                query=query,
                room_name=room_name,
                recall_mode=recall_mode,
                top_k=top_k,
                context=context if context else None
            )

            results = result.get("results", [])
            if not results:
                return "No relevant context found."

            output_lines = [f"Recalled {len(results)} memories ({recall_mode} mode):"]
            for r in results:
                output_lines.append(f"\n**{r.title}** ({r.store}) [score: {r.relevance_score:.2f}]")
                if r.summary:
                    output_lines.append(r.summary[:300] + ("..." if len(r.summary) > 300 else ""))

            return "\n".join(output_lines)

        else:
            # LocalAdapter fallback
            results = adapter.search(query=query, store="all", top_k=top_k)

            if not results:
                return "No relevant context found."

            output_lines = ["Relevant context:"]
            for note in results:
                output_lines.append(f"\n**{note.title}** ({note.store})")
                if note.body:
                    output_lines.append(note.body[:500] + ("..." if len(note.body) > 500 else ""))

            return "\n".join(output_lines)

    except Exception as e:
        return f"Error recalling context: {str(e)}"


@tool
def memx_resolve(
    note_id: str,
    store: str,
    resolve_action: str,
    room_name: str,
    target_store: str = "",
    entity_name: str = ""
) -> str:
    """
    Resolve a note with action (promote, archive, link, summarize).

    Phase 2: Manage note lifecycle.

    Args:
        note_id: Note ID to resolve
        store: Current store (short, journal, knowledge)
        resolve_action: Action to take
            - promote: Promote to knowledge (short->knowledge)
            - archive: Archive the note (journal->archive)
            - link: Link to existing entity
            - summarize: Create summary
        room_name: Current room name
        target_store: Target store for promote/archive (optional)
        entity_name: Entity name for promote/link (optional)

    Returns:
        Resolution result message
    """
    try:
        from adapters import get_memory_adapter, MemxAdapter

        adapter = get_memory_adapter(room_name)

        # MemxAdapter のみ resolve 対応
        if not isinstance(adapter, MemxAdapter):
            return f"Resolve requires memx connection. Current adapter: {type(adapter).__name__}"

        if not adapter.is_available():
            return "memx API is not available for resolve operation."

        # metadata 構築
        metadata = {}
        if entity_name:
            metadata["entity_name"] = entity_name

        result = adapter.resolve(
            note_id=note_id,
            store=store,
            resolve_action=resolve_action,
            target_store=target_store if target_store else None,
            metadata=metadata if metadata else None
        )

        if not result:
            return f"Resolve failed: {note_id}"

        output_lines = [
            f"Resolved: {result['action_taken']}",
            f"Original: {result['original_id']} ({store})",
            f"New: {result['id']} ({result['store']})",
            f"Status: {result['status']}"
        ]

        if result.get("linked_entities"):
            output_lines.append(f"Linked entities: {', '.join(result['linked_entities'])}")

        return "\n".join(output_lines)

    except Exception as e:
        return f"Error resolving note: {str(e)}\n{traceback.format_exc()}"


@tool
def memx_gc(
    mode: str,
    room_name: str,
    stores: str = "short,journal",
    age_days_min: int = 30
) -> str:
    """
    Garbage collection for memory cleanup.

    Phase 2: Manage memory lifecycle with safety checks.

    Args:
        mode: GC mode
            - dry-run: Preview candidates (safe, no deletion)
            - execute: Actually delete candidates (requires gc_execute_enabled=true)
        room_name: Current room name
        stores: Comma-separated list of stores to target (default: short,journal)
        age_days_min: Minimum age in days for GC candidates (default: 30)

    Returns:
        GC result message
    """
    try:
        import config_manager
        from adapters import get_memory_adapter, MemxAdapter

        adapter = get_memory_adapter(room_name)

        # MemxAdapter のみ GC 対応
        if not isinstance(adapter, MemxAdapter):
            return f"GC requires memx connection. Current adapter: {type(adapter).__name__}"

        if not adapter.is_available():
            return "memx API is not available for GC operation."

        # execute モードの安全確認
        if mode == "execute":
            memx_settings = config_manager.CONFIG_GLOBAL.get("memx_settings", {})
            if not memx_settings.get("gc_execute_enabled", False):
                return "GC execute mode is disabled. Set gc_execute_enabled=true in config."

        # gc_scope 構築
        gc_scope = {
            "stores": [s.strip() for s in stores.split(",")],
            "criteria": {
                "age_days_min": age_days_min,
                "access_count_max": 0,
                "exclude_tags": ["important", "persistent"]
            }
        }

        result = adapter.gc(
            mode=mode,
            room_name=room_name,
            gc_scope=gc_scope
        )

        if not result:
            return "GC operation returned no result."

        if result.get("error"):
            return f"GC error [{result['error']}]: {result.get('message', 'Unknown error')}"

        if mode == "dry-run":
            candidates = result.get("candidates", [])
            output_lines = [
                f"GC dry-run result:",
                f"  Total candidates: {result['total_candidates']}",
                f"  Would delete: {result['would_delete']}",
                f"  Safety checks passed: {result['safety_checks_passed']}"
            ]

            if candidates:
                output_lines.append("\nCandidates:")
                for c in candidates[:10]:  # 最大10件表示
                    output_lines.append(f"  - {c['note_id']}: {c['title'][:50]} ({c['reason']})")

                if len(candidates) > 10:
                    output_lines.append(f"  ... and {len(candidates) - 10} more")

            return "\n".join(output_lines)

        else:
            return (
                f"GC execute result:\n"
                f"  Deleted: {result['deleted_count']}\n"
                f"  Archived: {len(result['archived_ids'])}\n"
                f"  Errors: {len(result['errors'])}\n"
                f"  Timestamp: {result['timestamp']}"
            )

    except Exception as e:
        return f"Error during GC: {str(e)}\n{traceback.format_exc()}"
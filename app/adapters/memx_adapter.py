# adapters/memx_adapter.py
"""
MemxAdapter - memx-resolver API を使用する記憶アダプター

Phase 1: ingest/search/show
Phase 2: recall/resolve/gc
"""

from typing import List, Optional, Dict, Any
from adapters.memory_adapter import MemoryAdapter, MemoryNote


class MemxAdapter(MemoryAdapter):
    """
    memx-resolver API を使用する記憶アダプター
    """

    def __init__(self, api_addr: str = None, db_path: str = None, timeout: int = None):
        """
        Initialize MemxAdapter.

        Args:
            api_addr: API endpoint (default: from env/config)
            db_path: Database path (default: from room)
            timeout: Request timeout in seconds (default: 10)
        """
        self._api_addr = api_addr
        self._db_path = db_path
        self._timeout = timeout
        self._client = None
        self._available = None

    def _get_client(self):
        """Get or create memx client."""
        if self._client is None:
            from memx_client import MemxClient
            self._client = MemxClient(
                api_addr=self._api_addr,
                db_path=self._db_path,
                timeout=self._timeout
            )
        return self._client

    def is_available(self) -> bool:
        """Check if memx API is reachable."""
        if self._available is not None:
            return self._available

        try:
            client = self._get_client()
            self._available = client.health_check()
            return self._available
        except Exception as e:
            print(f"[MemxAdapter] Health check failed: {e}")
            self._available = False
            return False

    def ingest(
        self,
        store: str,
        title: str,
        body: str,
        summary: str = "",
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> MemoryNote:
        """Save memory via memx API."""
        from memx_client import MemxAPIError, MemxConnectionError

        try:
            client = self._get_client()

            # store に応じて source_type を設定
            source_type = kwargs.get("source_type", store)

            note = client.ingest(
                store=store,
                title=title,
                body=body,
                summary=summary,
                source_type=source_type,
                tags=tags or [],
                **{k: v for k, v in kwargs.items() if k != "source_type"}
            )

            return MemoryNote(
                id=note.id,
                title=note.title,
                body=note.body,
                summary=note.summary,
                store=store,
                created_at=note.created_at,
                updated_at=note.updated_at,
                tags=tags or []
            )

        except MemxConnectionError as e:
            print(f"[MemxAdapter] Connection error during ingest: {e}")
            raise
        except MemxAPIError as e:
            print(f"[MemxAdapter] API error during ingest: {e}")
            raise

    def search(
        self,
        query: str,
        store: str = "all",
        top_k: int = 10
    ) -> List[MemoryNote]:
        """Search memories via memx API."""
        from memx_client import MemxAPIError, MemxConnectionError

        try:
            client = self._get_client()
            notes = client.search(query=query, store=store, top_k=top_k)

            return [
                MemoryNote(
                    id=n.id,
                    title=n.title,
                    body=n.body,
                    summary=n.summary,
                    store=store,
                    created_at=n.created_at,
                    updated_at=n.updated_at,
                    tags=[]
                )
                for n in notes
            ]

        except MemxConnectionError as e:
            print(f"[MemxAdapter] Connection error during search: {e}")
            return []
        except MemxAPIError as e:
            print(f"[MemxAdapter] API error during search: {e}")
            return []

    def show(self, note_id: str, store: str = "short") -> Optional[MemoryNote]:
        """Get specific memory via memx API."""
        from memx_client import MemxAPIError, MemxConnectionError

        try:
            client = self._get_client()
            note = client.show(note_id, store=store)

            return MemoryNote(
                id=note.id,
                title=note.title,
                body=note.body,
                summary=note.summary,
                store=store,
                created_at=note.created_at,
                updated_at=note.updated_at,
                tags=[]
            )

        except MemxConnectionError as e:
            print(f"[MemxAdapter] Connection error during show: {e}")
            return None
        except MemxAPIError as e:
            if e.code == "NOT_FOUND":
                return None
            print(f"[MemxAdapter] API error during show: {e}")
            return None

    # ===== Phase 2: recall/resolve/gc =====

    def recall(
        self,
        query: str,
        room_name: str,
        recall_mode: str = "relevant",
        top_k: int = 5,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Recall notes with context-aware search.

        Args:
            query: Search query
            room_name: Room name
            recall_mode: recent, relevant, related
            top_k: Maximum results
            context: Optional context

        Returns:
            Dict with results list
        """
        from memx_client import MemxAPIError, MemxConnectionError

        try:
            client = self._get_client()
            result = client.recall(
                query=query,
                room_name=room_name,
                recall_mode=recall_mode,
                top_k=top_k,
                context=context
            )
            print(f"[MemxAdapter] Recall: {result['total_count']} results for room: {room_name}")
            return result

        except MemxConnectionError as e:
            print(f"[MemxAdapter] Connection error during recall: {e}")
            return {"results": [], "total_count": 0, "recall_source": "error"}
        except MemxAPIError as e:
            print(f"[MemxAdapter] API error during recall: {e}")
            return {"results": [], "total_count": 0, "recall_source": "error"}

    def resolve(
        self,
        note_id: str,
        store: str,
        resolve_action: str,
        target_store: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Resolve a note with action.

        Args:
            note_id: Note ID to resolve
            store: Current store
            resolve_action: promote, archive, link, summarize
            target_store: Target store for promote/archive
            metadata: Optional metadata

        Returns:
            Dict with resolved_note info or None
        """
        from memx_client import MemxAPIError, MemxConnectionError

        try:
            client = self._get_client()
            result = client.resolve(
                note_id=note_id,
                store=store,
                resolve_action=resolve_action,
                target_store=target_store,
                metadata=metadata
            )
            print(f"[MemxAdapter] Resolve: {resolve_action} {note_id} -> {result.store}")
            return {
                "id": result.id,
                "original_id": result.original_id,
                "store": result.store,
                "status": result.status,
                "action_taken": result.action_taken,
                "linked_entities": result.linked_entities
            }

        except MemxConnectionError as e:
            print(f"[MemxAdapter] Connection error during resolve: {e}")
            return None
        except MemxAPIError as e:
            print(f"[MemxAdapter] API error during resolve: {e}")
            return None

    def gc(
        self,
        mode: str,
        room_name: str,
        gc_scope: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Execute garbage collection.

        Args:
            mode: dry-run or execute
            room_name: Room name
            gc_scope: Scope definition (stores, criteria)

        Returns:
            Dict with GC result or None
        """
        from memx_client import MemxAPIError, MemxConnectionError

        try:
            client = self._get_client()
            result = client.gc(
                mode=mode,
                room_name=room_name,
                gc_scope=gc_scope
            )

            if mode == "dry-run":
                print(f"[MemxAdapter] GC dry-run: {result.total_candidates} candidates, safety_checks={result.safety_checks_passed}")
                return {
                    "mode": "dry-run",
                    "candidates": [
                        {
                            "note_id": c.note_id,
                            "title": c.title,
                            "store": c.store,
                            "reason": c.reason,
                            "age_days": c.age_days,
                            "access_count": c.access_count
                        }
                        for c in result.candidates
                    ],
                    "total_candidates": result.total_candidates,
                    "would_delete": result.would_delete,
                    "safety_checks_passed": result.safety_checks_passed
                }
            else:
                print(f"[MemxAdapter] GC execute: deleted={result.deleted_count}, archived={len(result.archived_ids)}")
                return {
                    "mode": "execute",
                    "deleted_count": result.deleted_count,
                    "deleted_ids": result.deleted_ids,
                    "archived_ids": result.archived_ids,
                    "errors": result.errors,
                    "timestamp": result.timestamp
                }

        except MemxConnectionError as e:
            print(f"[MemxAdapter] Connection error during GC: {e}")
            return None
        except MemxAPIError as e:
            if e.code == "GC_FORBIDDEN":
                print(f"[MemxAdapter] GC forbidden: {e.message}")
            else:
                print(f"[MemxAdapter] API error during GC: {e}")
            return {"mode": mode, "error": e.code, "message": e.message}
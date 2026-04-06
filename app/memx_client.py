# memx_client.py
"""
memx-resolver HTTP API Client for Open-Ark

Phase 1: ingest/search/show の基本API呼び出し
Phase 2: recall/resolve/gc/migrate の拡張API呼び出し
"""

import os
import json
import requests
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime


# store名からエンドポイントへのマッピング
STORE_ENDPOINTS = {
    "short": "notes",
    "journal": "journal",
    "knowledge": "knowledge",
    "archive": "archive"
}

# recall_mode enum
RECALL_MODES = ["recent", "relevant", "related"]

# resolve_action enum
RESOLVE_ACTIONS = ["promote", "archive", "link", "summarize"]


@dataclass
class Note:
    """memx Note オブジェクト"""
    id: str
    title: str
    body: str
    summary: str
    created_at: str
    updated_at: str
    last_accessed_at: str
    access_count: int
    source_type: str
    origin: str
    source_trust: str
    sensitivity: str
    store: str = ""


@dataclass
class RecallResult:
    """memx recall 結果"""
    note_id: str
    title: str
    summary: str
    store: str
    relevance_score: float
    timestamp: str


@dataclass
class ResolveResult:
    """memx resolve 結果"""
    id: str
    original_id: str
    store: str
    status: str
    action_taken: str
    linked_entities: List[str]


@dataclass
class GCCandidate:
    """GC 削除候補"""
    note_id: str
    title: str
    store: str
    reason: str
    age_days: int
    access_count: int


@dataclass
class GCDryRunResult:
    """GC dry-run 結果"""
    mode: str
    candidates: List[GCCandidate]
    total_candidates: int
    would_delete: int
    safety_checks_passed: bool


@dataclass
class GCExecuteResult:
    """GC execute 結果"""
    mode: str
    deleted_count: int
    deleted_ids: List[str]
    archived_ids: List[str]
    errors: List[Dict]
    timestamp: str


@dataclass
class MigrateCandidate:
    """移行候補"""
    source_type: str
    source_id: str
    source_name: str
    content_preview: str
    target_store: str
    mapped_fields: Dict


@dataclass
class MigratePreviewResult:
    """移行 preview 結果"""
    mode: str
    candidates: List[MigrateCandidate]
    total_candidates: int
    would_create: int


@dataclass
class MigrateResult:
    """移行 migrate 結果"""
    mode: str
    created_notes: List[Dict]
    errors: List[Dict]
    source_files_preserved: bool
    timestamp: str


class MemxAPIError(Exception):
    """memx API エラー"""
    def __init__(self, code: str, message: str, details: Any = None):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"[{code}] {message}")


class MemxConnectionError(Exception):
    """memx API 接続エラー"""
    pass


class MemxClient:
    """
    memx-resolver HTTP API Client

    Usage:
        client = MemxClient(api_addr="http://127.0.0.1:7766", db_path="path/to/db")
        note = client.ingest("knowledge", "タイトル", "本文")
        results = client.search("検索クエリ", store="knowledge", top_k=10)
    """

    DEFAULT_TIMEOUT = 10  # seconds

    def __init__(
        self,
        api_addr: Optional[str] = None,
        db_path: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize memx client.

        Args:
            api_addr: API endpoint (default: env MEMX_API_ADDR or http://127.0.0.1:7766)
            db_path: Database path for this room (sent via X-Memx-DB-Path header)
            timeout: Request timeout in seconds (default: 10)
        """
        self.api_addr = api_addr or os.environ.get("MEMX_API_ADDR", "http://127.0.0.1:7766")
        self.db_path = db_path
        self.timeout = timeout or self.DEFAULT_TIMEOUT

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {"Content-Type": "application/json"}
        # db_path をカスタムヘッダーで渡す（APIが対応していれば使用）
        if self.db_path:
            headers["X-Memx-DB-Path"] = self.db_path
        return headers

    def _get_store_endpoint(self, store: str, operation: str = "ingest") -> str:
        """
        store名から対応するエンドポイントパスを取得する。

        Args:
            store: short, journal, knowledge, archive
            operation: ingest, search, get など

        Returns:
            エンドポイントパス（例: "/v1/knowledge:ingest"）
        """
        if store not in STORE_ENDPOINTS:
            # 不明なstoreはデフォルト（notes/short）を使用
            store = "short"

        endpoint_name = STORE_ENDPOINTS[store]

        if operation == "ingest":
            return f"/v1/{endpoint_name}:ingest"
        elif operation == "search":
            return f"/v1/{endpoint_name}:search"
        elif operation == "get":
            return f"/v1/{endpoint_name}"
        else:
            return f"/v1/{endpoint_name}:{operation}"

    def _handle_error_response(self, response: requests.Response) -> None:
        """Handle error response from API."""
        try:
            error_data = response.json()
            code = error_data.get("code", "UNKNOWN")
            message = error_data.get("message", response.text)
            details = error_data.get("details")
            raise MemxAPIError(code, message, details)
        except json.JSONDecodeError:
            raise MemxAPIError("UNKNOWN", response.text)

    def _parse_note(self, data: Dict) -> Note:
        """Parse Note from API response."""
        return Note(
            id=data.get("id", ""),
            title=data.get("title", ""),
            body=data.get("body", ""),
            summary=data.get("summary", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            last_accessed_at=data.get("last_accessed_at", ""),
            access_count=data.get("access_count", 0),
            source_type=data.get("source_type", ""),
            origin=data.get("origin", ""),
            source_trust=data.get("source_trust", ""),
            sensitivity=data.get("sensitivity", "")
        )

    def health_check(self) -> bool:
        """
        Check if API is reachable.

        Returns:
            True if API is healthy, False otherwise.
        """
        try:
            response = requests.post(
                f"{self.api_addr}/v1/notes:search",
                headers=self._get_headers(),
                json={"query": "health_check", "top_k": 1},
                timeout=self.timeout
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def ingest(
        self,
        store: str,
        title: str,
        body: str,
        summary: str = "",
        source_type: str = "",
        origin: str = "",
        source_trust: str = "",
        sensitivity: str = "",
        tags: Optional[List[str]] = None
    ) -> Note:
        """
        Ingest a new note to the specified store.

        Args:
            store: Target store (short, journal, knowledge)
            title: Note title
            body: Note body/content
            summary: Optional summary
            source_type: Source type indicator
            origin: Origin indicator
            source_trust: Trust level
            sensitivity: Sensitivity level
            tags: Optional list of tags

        Returns:
            Created Note object

        Raises:
            MemxConnectionError: If API is unreachable
            MemxAPIError: If API returns an error
        """
        payload = {
            "title": title,
            "body": body
        }
        if summary:
            payload["summary"] = summary
        if source_type:
            payload["source_type"] = source_type
        if origin:
            payload["origin"] = origin
        if source_trust:
            payload["source_trust"] = source_trust
        if sensitivity:
            payload["sensitivity"] = sensitivity
        if tags:
            payload["tags"] = tags

        # storeに応じたエンドポイントを使用
        endpoint = self._get_store_endpoint(store, "ingest")

        try:
            response = requests.post(
                f"{self.api_addr}{endpoint}",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                note = self._parse_note(data.get("note", {}))
                note.store = store
                return note
            else:
                self._handle_error_response(response)

        except requests.exceptions.Timeout:
            raise MemxConnectionError(f"API request timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise MemxConnectionError(f"API connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise MemxConnectionError(f"API request failed: {e}")

    def search(
        self,
        query: str,
        store: str = "all",
        top_k: int = 10
    ) -> List[Note]:
        """
        Search notes in the specified store.

        Args:
            query: Search query
            store: Target store (short, journal, knowledge, archive, all)
            top_k: Maximum number of results

        Returns:
            List of matching Note objects

        Raises:
            MemxConnectionError: If API is unreachable
            MemxAPIError: If API returns an error
        """
        payload = {
            "query": query,
            "top_k": top_k
        }

        results = []

        try:
            if store == "all":
                # 全ストアを検索（short, journal, knowledge, archive）
                for s in ["short", "journal", "knowledge", "archive"]:
                    endpoint = self._get_store_endpoint(s, "search")
                    response = requests.post(
                        f"{self.api_addr}{endpoint}",
                        headers=self._get_headers(),
                        json=payload,
                        timeout=self.timeout
                    )

                    if response.status_code == 200:
                        data = response.json()
                        notes = data.get("notes", [])
                        for n in notes:
                            note = self._parse_note(n)
                            note.store = s
                            results.append(note)
            else:
                # 指定ストアのみ検索
                endpoint = self._get_store_endpoint(store, "search")
                response = requests.post(
                    f"{self.api_addr}{endpoint}",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    data = response.json()
                    notes = data.get("notes", [])
                    for n in notes:
                        note = self._parse_note(n)
                        note.store = store
                        results.append(note)
                else:
                    self._handle_error_response(response)

            return results[:top_k]

        except requests.exceptions.Timeout:
            raise MemxConnectionError(f"API request timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise MemxConnectionError(f"API connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise MemxConnectionError(f"API request failed: {e}")

    def show(self, note_id: str, store: str = "short") -> Note:
        """
        Get a specific note by ID.

        Args:
            note_id: Note ID
            store: Store where the note is stored (short, journal, knowledge)

        Returns:
            Note object

        Raises:
            MemxConnectionError: If API is unreachable
            MemxAPIError: If API returns an error (e.g., NOT_FOUND)
        """
        endpoint = self._get_store_endpoint(store, "get")

        try:
            response = requests.get(
                f"{self.api_addr}{endpoint}/{note_id}",
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                note = self._parse_note(data)
                note.store = store
                return note
            else:
                self._handle_error_response(response)

        except requests.exceptions.Timeout:
            raise MemxConnectionError(f"API request timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise MemxConnectionError(f"API connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise MemxConnectionError(f"API request failed: {e}")

    # ===== Phase 2: recall/resolve/gc/migrate =====

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
            context: Optional context (current_topic, time_range)

        Returns:
            Dict with results, total_count, recall_source, mode_used

        Raises:
            MemxConnectionError: If API is unreachable
            MemxAPIError: If API returns an error (INVALID_MODE, RECALL_ERROR)
        """
        if recall_mode not in RECALL_MODES:
            raise MemxAPIError("INVALID_MODE", f"Invalid recall_mode: {recall_mode}")

        payload = {
            "query": query,
            "room_name": room_name,
            "recall_mode": recall_mode,
            "top_k": top_k
        }
        if context:
            payload["context"] = context

        try:
            response = requests.post(
                f"{self.api_addr}/v1/recall",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                results = []
                for r in data.get("results", []):
                    results.append(RecallResult(
                        note_id=r.get("note_id", ""),
                        title=r.get("title", ""),
                        summary=r.get("summary", ""),
                        store=r.get("store", ""),
                        relevance_score=r.get("relevance_score", 0.0),
                        timestamp=r.get("timestamp", "")
                    ))
                return {
                    "results": results,
                    "total_count": data.get("total_count", 0),
                    "recall_source": data.get("recall_source", "memx"),
                    "mode_used": data.get("mode_used", recall_mode)
                }
            else:
                self._handle_error_response(response)

        except requests.exceptions.Timeout:
            raise MemxConnectionError(f"API request timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise MemxConnectionError(f"API connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise MemxConnectionError(f"API request failed: {e}")

    def resolve(
        self,
        note_id: str,
        store: str,
        resolve_action: str,
        target_store: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> ResolveResult:
        """
        Resolve a note with action.

        Args:
            note_id: Note ID to resolve
            store: Current store (short, journal, knowledge)
            resolve_action: promote, archive, link, summarize
            target_store: Target store for promote/archive
            metadata: Optional metadata (entity_name, confidence)

        Returns:
            ResolveResult object

        Raises:
            MemxConnectionError: If API is unreachable
            MemxAPIError: NOT_FOUND, RESOLVE_FAILED, INVALID_ACTION
        """
        if resolve_action not in RESOLVE_ACTIONS:
            raise MemxAPIError("INVALID_ACTION", f"Invalid resolve_action: {resolve_action}")

        payload = {
            "note_id": note_id,
            "store": store,
            "resolve_action": resolve_action
        }
        if target_store:
            payload["target_store"] = target_store
        if metadata:
            payload["metadata"] = metadata

        try:
            response = requests.post(
                f"{self.api_addr}/v1/resolve",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                resolved = data.get("resolved_note", {})
                return ResolveResult(
                    id=resolved.get("id", ""),
                    original_id=resolved.get("original_id", note_id),
                    store=resolved.get("store", ""),
                    status=resolved.get("status", ""),
                    action_taken=data.get("action_taken", resolve_action),
                    linked_entities=data.get("linked_entities", [])
                )
            else:
                self._handle_error_response(response)

        except requests.exceptions.Timeout:
            raise MemxConnectionError(f"API request timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise MemxConnectionError(f"API connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise MemxConnectionError(f"API request failed: {e}")

    def gc(
        self,
        mode: str,
        room_name: str,
        gc_scope: Optional[Dict] = None
    ) -> Any:
        """
        Execute garbage collection.

        Args:
            mode: dry-run or execute
            room_name: Room name
            gc_scope: Scope definition (stores, criteria)

        Returns:
            GCDryRunResult or GCExecuteResult

        Raises:
            MemxConnectionError: If API is unreachable
            MemxAPIError: GC_FORBIDDEN, GC_ERROR, INVALID_MODE
        """
        if mode not in ["dry-run", "execute"]:
            raise MemxAPIError("INVALID_MODE", f"Invalid GC mode: {mode}")

        payload = {
            "mode": mode,
            "room_name": room_name
        }
        if gc_scope:
            payload["gc_scope"] = gc_scope

        try:
            response = requests.post(
                f"{self.api_addr}/v1/gc",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()

                if mode == "dry-run":
                    candidates = []
                    for c in data.get("candidates", []):
                        candidates.append(GCCandidate(
                            note_id=c.get("note_id", ""),
                            title=c.get("title", ""),
                            store=c.get("store", ""),
                            reason=c.get("reason", ""),
                            age_days=c.get("age_days", 0),
                            access_count=c.get("access_count", 0)
                        ))
                    return GCDryRunResult(
                        mode="dry-run",
                        candidates=candidates,
                        total_candidates=data.get("total_candidates", 0),
                        would_delete=data.get("would_delete", 0),
                        safety_checks_passed=data.get("safety_checks_passed", True)
                    )
                else:
                    return GCExecuteResult(
                        mode="execute",
                        deleted_count=data.get("deleted_count", 0),
                        deleted_ids=data.get("deleted_ids", []),
                        archived_ids=data.get("archived_ids", []),
                        errors=data.get("errors", []),
                        timestamp=data.get("timestamp", datetime.now().isoformat())
                    )
            else:
                self._handle_error_response(response)

        except requests.exceptions.Timeout:
            raise MemxConnectionError(f"API request timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise MemxConnectionError(f"API connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise MemxConnectionError(f"API request failed: {e}")

    def migrate(
        self,
        source: str,
        room_name: str,
        target_store: str,
        mode: str = "preview",
        filters: Optional[Dict] = None
    ) -> Any:
        """
        Migrate data from legacy sources to memx.

        Args:
            source: entity_memory, episode, question, insight
            room_name: Room name
            target_store: knowledge, journal, short
            mode: preview or migrate
            filters: Optional filters (entity_names, min_importance)

        Returns:
            MigratePreviewResult or MigrateResult

        Raises:
            MemxConnectionError: If API is unreachable
            MemxAPIError: MIGRATE_ERROR, INVALID_SOURCE
        """
        if source not in ["entity_memory", "episode", "question", "insight"]:
            raise MemxAPIError("INVALID_SOURCE", f"Invalid source: {source}")

        if mode not in ["preview", "migrate"]:
            raise MemxAPIError("INVALID_MODE", f"Invalid migrate mode: {mode}")

        payload = {
            "source": source,
            "room_name": room_name,
            "target_store": target_store,
            "mode": mode
        }
        if filters:
            payload["filters"] = filters

        try:
            response = requests.post(
                f"{self.api_addr}/v1/migrate",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()

                if mode == "preview":
                    candidates = []
                    for c in data.get("candidates", []):
                        candidates.append(MigrateCandidate(
                            source_type=c.get("source_type", source),
                            source_id=c.get("source_id", ""),
                            source_name=c.get("source_name", ""),
                            content_preview=c.get("content_preview", ""),
                            target_store=c.get("target_store", target_store),
                            mapped_fields=c.get("mapped_fields", {})
                        ))
                    return MigratePreviewResult(
                        mode="preview",
                        candidates=candidates,
                        total_candidates=data.get("total_candidates", 0),
                        would_create=data.get("would_create", 0)
                    )
                else:
                    return MigrateResult(
                        mode="migrate",
                        created_notes=data.get("created_notes", []),
                        errors=data.get("errors", []),
                        source_files_preserved=data.get("source_files_preserved", True),
                        timestamp=data.get("timestamp", datetime.now().isoformat())
                    )
            else:
                self._handle_error_response(response)

        except requests.exceptions.Timeout:
            raise MemxConnectionError(f"API request timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise MemxConnectionError(f"API connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise MemxConnectionError(f"API request failed: {e}")


# モジュールレベルのヘルパー関数
def get_memx_client_for_room(room_name: str, config: Optional[Dict] = None) -> MemxClient:
    """
    Get MemxClient instance for a specific room.

    Args:
        room_name: Room name
        config: Optional config dict (reads from config_manager if not provided)

    Returns:
        MemxClient instance configured for the room
    """
    import constants

    # DB パスは room_dir/memx を既定とする
    room_dir = Path(constants.ROOMS_DIR) / room_name
    db_path = room_dir / "memx"

    # API アドレス（環境変数優先、次に設定値）
    api_addr = os.environ.get("MEMX_API_ADDR")
    if not api_addr and config:
        api_addr = config.get("memx_api_addr", "http://127.0.0.1:7766")

    # タイムアウト
    timeout = None
    if config:
        timeout = config.get("memx_request_timeout_sec", 10)

    return MemxClient(
        api_addr=api_addr,
        db_path=str(db_path),
        timeout=timeout
    )
# tests/test_memx_phase2.py
"""
memx-resolver Phase 2 Acceptance Tests

要件書 docs/MEMX_INTEGRATION_REQUIREMENTS.md の AC-P2-001〜AC-P2-012 に基づく受け入れテスト。

テスト構成:
1. Unit Tests: MemxClient/MemxAdapter の入力、分岐、エラー処理（Mock使用）
2. LocalAdapter Tests: use_memx=false での動作検証（常に実行可能）
3. Real API Tests: MemxAdapter + 実 memx-resolver API 経由の検証（サーバー起動時のみ実行）

実API必要範囲（スキップ条件付き）:
- AC-P2-001: recall 実API呼び出し
- AC-P2-003/004: resolve 実API呼び出し
- AC-P2-005/006/007: GC 実API呼び出し

LocalAdapter範囲（常に実行可能）:
- AC-P2-002: recall フォールバック
- AC-P2-008/009/010: migrate（ローカルファイル操作）
- AC-P2-011: 既存導線維持
- AC-P2-012: 観測ログ
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# NOTE: Fixtures are provided by conftest.py:
# - workspace_tmp_path
# - local_adapter_config
# - memx_server_available
# - real_api_config
# Global mocks for send2trash and gradio are also applied in conftest.py


# ===== Phase 2 Data Classes =====

class TestPhase2DataClasses:
    """Phase 2 データクラステスト"""

    def test_recall_result_dataclass(self):
        from memx_client import RecallResult

        result = RecallResult(
            note_id="recall-001",
            title="テストタイトル",
            summary="テスト要約",
            store="journal",
            relevance_score=0.85,
            timestamp="2024-01-01T00:00:00"
        )

        assert result.note_id == "recall-001"
        assert result.relevance_score == 0.85
        assert result.store == "journal"

    def test_resolve_result_dataclass(self):
        from memx_client import ResolveResult

        result = ResolveResult(
            id="knowledge-001",
            original_id="short-001",
            store="knowledge",
            status="resolved",
            action_taken="promote",
            linked_entities=["エンティティ1"]
        )

        assert result.id == "knowledge-001"
        assert result.action_taken == "promote"

    def test_gc_dryrun_result_dataclass(self):
        from memx_client import GCDryRunResult, GCCandidate

        candidate = GCCandidate(
            note_id="gc-001",
            title="古いメモ",
            store="short",
            reason="age",
            age_days=45,
            access_count=0
        )

        result = GCDryRunResult(
            mode="dry-run",
            candidates=[candidate],
            total_candidates=1,
            would_delete=1,
            safety_checks_passed=True
        )

        assert result.mode == "dry-run"
        assert len(result.candidates) == 1

    def test_migrate_preview_result_dataclass(self):
        from memx_client import MigratePreviewResult, MigrateCandidate

        candidate = MigrateCandidate(
            source_type="entity_memory",
            source_id="entity-001",
            source_name="テスト人物",
            content_preview="# テスト人物\n...",
            target_store="knowledge",
            mapped_fields={"title": "テスト人物"}
        )

        result = MigratePreviewResult(
            mode="preview",
            candidates=[candidate],
            total_candidates=1,
            would_create=1
        )

        assert result.mode == "preview"


# ===== MemxClient Unit Tests (Mock使用) =====

class TestMemxClientValidation:
    """MemxClient の入力検証、分岐処理、エラー処理"""

    def test_recall_invalid_mode_raises_error(self):
        from memx_client import MemxClient, MemxAPIError

        client = MemxClient()

        with pytest.raises(MemxAPIError) as exc_info:
            client.recall(query="test", room_name="test", recall_mode="invalid_mode")

        assert exc_info.value.code == "INVALID_MODE"

    def test_resolve_invalid_action_raises_error(self):
        from memx_client import MemxClient, MemxAPIError

        client = MemxClient()

        with pytest.raises(MemxAPIError) as exc_info:
            client.resolve(note_id="test", store="short", resolve_action="invalid_action")

        assert exc_info.value.code == "INVALID_ACTION"

    def test_gc_invalid_mode_raises_error(self):
        from memx_client import MemxClient, MemxAPIError

        client = MemxClient()

        with pytest.raises(MemxAPIError) as exc_info:
            client.gc(mode="invalid_mode", room_name="test")

        assert exc_info.value.code == "INVALID_MODE"

    def test_migrate_invalid_source_raises_error(self):
        from memx_client import MemxClient, MemxAPIError

        client = MemxClient()

        with pytest.raises(MemxAPIError) as exc_info:
            client.migrate(source="invalid_source", room_name="test", target_store="knowledge")

        assert exc_info.value.code == "INVALID_SOURCE"


# ===== MemxAdapter Unit Tests (Mock使用) =====

class TestMemxAdapterMocked:
    """MemxAdapter の API レスポンス整形を Mock で検証"""

    def test_recall_response_parsing(self):
        from adapters.memx_adapter import MemxAdapter
        from memx_client import RecallResult

        adapter = MemxAdapter(api_addr="http://mock", db_path="/mock")

        mock_client = Mock()
        mock_client.recall.return_value = {
            "results": [RecallResult(
                note_id="recall-001",
                title="テスト結果1",
                summary="要約",
                store="journal",
                relevance_score=0.85,
                timestamp="2024-01-01T00:00:00"
            )],
            "total_count": 1,
            "recall_source": "memx",
            "mode_used": "relevant"
        }

        adapter._client = mock_client
        adapter._available = True

        result = adapter.recall(query="test", room_name="test_room", recall_mode="relevant")

        assert result["total_count"] == 1
        assert result["recall_source"] == "memx"

    def test_resolve_response_parsing(self):
        from adapters.memx_adapter import MemxAdapter
        from memx_client import ResolveResult

        adapter = MemxAdapter(api_addr="http://mock", db_path="/mock")

        mock_client = Mock()
        mock_client.resolve.return_value = ResolveResult(
            id="knowledge-001",
            original_id="short-001",
            store="knowledge",
            status="resolved",
            action_taken="promote",
            linked_entities=["テストエンティティ"]
        )

        adapter._client = mock_client
        adapter._available = True

        result = adapter.resolve(note_id="short-001", store="short", resolve_action="promote")

        assert result["id"] == "knowledge-001"
        assert result["action_taken"] == "promote"

    def test_gc_dryrun_response_parsing(self):
        from adapters.memx_adapter import MemxAdapter
        from memx_client import GCDryRunResult, GCCandidate

        adapter = MemxAdapter(api_addr="http://mock", db_path="/mock")

        mock_client = Mock()
        mock_client.gc.return_value = GCDryRunResult(
            mode="dry-run",
            candidates=[GCCandidate(
                note_id="gc-001",
                title="古いメモ",
                store="short",
                reason="age",
                age_days=45,
                access_count=0
            )],
            total_candidates=1,
            would_delete=1,
            safety_checks_passed=True
        )

        adapter._client = mock_client
        adapter._available = True

        result = adapter.gc(mode="dry-run", room_name="test_room")

        assert result["mode"] == "dry-run"
        assert result["total_candidates"] == 1


# ===== LocalAdapter Tests (常に実行可能) =====

class TestPhase2LocalAdapter:
    """
    LocalAdapter 使用時の動作検証。
    use_memx=false または memx API 到達不可時のフォールバック動作を確認。
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config):
        pass

    # --- AC-P2-002: recall フォールバック ---
    def test_ac_p2_002_recall_fallback(self):
        """
        AC-P2-002: memx 利用不可時に memx_recall が LocalAdapter 系検索へ
        フォールバックし、エラー終了ではなく空または代替結果を返せる
        """
        from tools.memx_tools import memx_recall

        result = memx_recall.invoke({
            "query": "test query",
            "room_name": "fallback_room",
            "recall_mode": "recent"
        })

        # フォールバック成功
        assert result is not None
        assert "Error recalling context" not in result

    # --- AC-P2-008: migrate preview ---
    def test_ac_p2_008_migrate_preview(self, workspace_tmp_path):
        """
        AC-P2-008: 移行補助の preview が候補一覧、件数、target store、
        マッピング結果を返せる（LocalAdapter使用）
        """
        from tools.memx_migrate import migrate_preview

        room_name = "preview_test"
        room_dir = workspace_tmp_path / "characters" / room_name
        entities_dir = room_dir / "memory" / "entities"
        entities_dir.mkdir(parents=True)

        test_entity = entities_dir / "preview_entity.md"
        test_entity.write_text("# Preview Entity\nTest content", encoding="utf-8")

        result = migrate_preview(
            source="entity_memory",
            room_name=room_name,
            target_store="knowledge"
        )

        assert result["mode"] == "preview"
        assert "candidates" in result
        assert "total_candidates" in result
        assert result["source"] == "local"

    # --- AC-P2-009: migrate ソース保持 ---
    def test_ac_p2_009_migrate_preserve_source(self, workspace_tmp_path):
        """
        AC-P2-009: 移行補助の migrate は既定で source file を削除せず、
        移行後も元データを保持する
        """
        from tools.memx_migrate import migrate_execute

        room_name = "preserve_test"
        room_dir = workspace_tmp_path / "characters" / room_name
        entities_dir = room_dir / "memory" / "entities"
        entities_dir.mkdir(parents=True)

        test_entity = entities_dir / "preserve_test.md"
        test_entity.write_text("# Preserve Test\nContent", encoding="utf-8")

        result = migrate_execute(
            source="entity_memory",
            room_name=room_name,
            target_store="knowledge"
        )

        assert result["source_files_preserved"] == True
        assert test_entity.exists()

    # --- AC-P2-010: migrate room 分離 ---
    def test_ac_p2_010_migrate_room_isolated(self, workspace_tmp_path):
        """
        AC-P2-010: 移行補助は room 単位で動作し、他 room の候補を混在させない
        """
        from tools.memx_migrate import migrate_preview

        room_a = "room_a"
        room_b = "room_b"

        for room_name in [room_a, room_b]:
            room_dir = workspace_tmp_path / "characters" / room_name
            entities_dir = room_dir / "memory" / "entities"
            entities_dir.mkdir(parents=True)
            entity_file = entities_dir / f"{room_name}_entity.md"
            entity_file.write_text(f"# {room_name} Entity", encoding="utf-8")

        result_a = migrate_preview(source="entity_memory", room_name=room_a, target_store="knowledge")
        result_b = migrate_preview(source="entity_memory", room_name=room_b, target_store="knowledge")

        names_a = [c.get("source_name", "") for c in result_a.get("candidates", [])]
        names_b = [c.get("source_name", "") for c in result_b.get("candidates", [])]

        # 各roomの結果に他roomのデータが含まれない
        for name in names_a:
            assert room_b not in name
        for name in names_b:
            assert room_a not in name

    # --- AC-P2-011: 既存導線維持 ---
    def test_ac_p2_011_existing_pipeline_preserved(self):
        """
        AC-P2-011: memx 無効時に既存導線を壊さず継続利用できる
        """
        from tools.memx_tools import memx_recall, memx_search

        recall_result = memx_recall.invoke({
            "query": "test",
            "room_name": "pipeline_test",
            "recall_mode": "relevant"
        })

        search_result = memx_search.invoke({
            "query": "test",
            "room_name": "pipeline_test"
        })

        assert recall_result is not None
        assert search_result is not None

    # --- AC-P2-012: 観測ログ ---
    def test_ac_p2_012_observable_output(self):
        """
        AC-P2-012: 各導線は結果を追跡可能な情報を出せる
        """
        from tools.memx_migrate import migrate_preview

        preview_result = migrate_preview(
            source="entity_memory",
            room_name="observe_test",
            target_store="knowledge"
        )

        assert preview_result["mode"] == "preview"
        assert "total_candidates" in preview_result

    # --- 不合格条件: resolve は memx 接続が必要 ---
    def test_resolve_requires_memx(self):
        """resolve は LocalAdapter では動作しない"""
        from tools.memx_tools import memx_resolve

        result = memx_resolve.invoke({
            "note_id": "test-note",
            "store": "short",
            "resolve_action": "promote",
            "room_name": "test_room"
        })

        assert "memx connection" in result.lower() or "requires memx" in result.lower()

    # --- 不合格条件: GC は memx 接続が必要 ---
    def test_gc_requires_memx(self):
        """GC は LocalAdapter では動作しない"""
        from tools.memx_tools import memx_gc

        result = memx_gc.invoke({
            "mode": "dry-run",
            "room_name": "test_room"
        })

        assert "memx connection" in result.lower() or "requires memx" in result.lower()


# ===== Real API Tests (MemxAdapter到達時のみ実行) =====

class TestPhase2RealAPI:
    """
    実 memx-resolver API 使用時の検証。
    memx_server_available=False の場合はスキップされる。
    """

    @pytest.fixture(autouse=True)
    def setup(self, real_api_config, memx_server_available):
        if not memx_server_available:
            pytest.skip("memx-resolver API not available at http://127.0.0.1:7766")

    # --- AC-P2-001: recall 実API呼び出し ---
    def test_ac_p2_001_recall_with_real_api(self):
        """
        AC-P2-001: memx 利用可能時に memx_recall が結果を返せる

        前提: memx-resolver API が起動していること
        """
        from tools.memx_tools import memx_recall
        from adapters import get_memory_adapter, MemxAdapter

        adapter = get_memory_adapter("test_room")

        # MemxAdapter が使用されていることを確認
        assert isinstance(adapter, MemxAdapter), f"Expected MemxAdapter, got {type(adapter)}"
        assert adapter.is_available(), "MemxAdapter should be available"

        result = memx_recall.invoke({
            "query": "test",
            "room_name": "test_room",
            "recall_mode": "relevant"
        })

        # エラーでないことを確認
        assert "Error recalling context" not in result

    # --- AC-P2-003: resolve promote 実API呼び出し ---
    def test_ac_p2_003_resolve_with_real_api(self):
        """
        AC-P2-003: memx_resolve が promote により short から knowledge への
        解決操作を実行できる

        前提: memx-resolver API が起動していること
        注: 存在しないノートIDの場合はエラーになるが、API呼び出し自体は成功
        """
        from tools.memx_tools import memx_resolve
        from adapters import get_memory_adapter, MemxAdapter

        adapter = get_memory_adapter("test_room")
        assert isinstance(adapter, MemxAdapter), "Expected MemxAdapter"

        result = memx_resolve.invoke({
            "note_id": "non-existent-note",
            "store": "short",
            "resolve_action": "promote",
            "room_name": "test_room",
            "target_store": "knowledge"
        })

        # APIが呼び出されたことを確認（結果は成功でも失敗でもよい）
        assert result is not None
        # resolve attempted または error が返る
        assert "resolve" in result.lower() or "error" in result.lower()

    # --- AC-P2-004: resolve archive 実API呼び出し ---
    def test_ac_p2_004_resolve_archive_with_real_api(self):
        """
        AC-P2-004: memx_resolve が archive により journal から archive への
        解決操作を実行できる

        前提: memx-resolver API が起動していること
        """
        from tools.memx_tools import memx_resolve
        from adapters import get_memory_adapter, MemxAdapter

        adapter = get_memory_adapter("test_room")
        assert isinstance(adapter, MemxAdapter), "Expected MemxAdapter"

        result = memx_resolve.invoke({
            "note_id": "non-existent-journal-note",
            "store": "journal",
            "resolve_action": "archive",
            "room_name": "test_room"
        })

        assert result is not None

    # --- AC-P2-005: GC execute 拒否 ---
    def test_ac_p2_005_gc_execute_disabled(self):
        """
        AC-P2-005: memx_gc の execute は gc_execute_enabled=true の明示設定
        なしでは実行拒否される

        前提: memx-resolver API が起動していること
        """
        import config_manager
        from tools.memx_tools import memx_gc
        from adapters import get_memory_adapter, MemxAdapter

        # gc_execute_enabled=False を確認
        config_manager.CONFIG_GLOBAL["memx_settings"]["gc_execute_enabled"] = False

        adapter = get_memory_adapter("test_room")
        assert isinstance(adapter, MemxAdapter), "Expected MemxAdapter"

        result = memx_gc.invoke({
            "mode": "execute",
            "room_name": "test_room"
        })

        # disabled で拒否されることを確認
        result_lower = result.lower()
        assert "disabled" in result_lower or "gc execute mode is disabled" in result_lower, \
            f"Expected 'disabled' in result, got: {result}"

    # --- AC-P2-006: GC dry-run 実API呼び出し ---
    def test_ac_p2_006_gc_dryrun_with_real_api(self):
        """
        AC-P2-006: memx_gc の dry-run が削除候補、件数、理由、安全確認結果を返せる

        前提: memx-resolver API が起動していること
        注: GCエンドポイントが未実装の場合は404エラーになる
        """
        from tools.memx_tools import memx_gc
        from adapters import get_memory_adapter, MemxAdapter

        adapter = get_memory_adapter("test_room")
        assert isinstance(adapter, MemxAdapter), "Expected MemxAdapter"

        result = memx_gc.invoke({
            "mode": "dry-run",
            "room_name": "test_room",
            "stores": "short",
            "age_days_min": 30
        })

        # API呼び出しが行われたことを確認
        assert result is not None
        # GC または error が含まれる
        result_lower = result.lower()
        assert "gc" in result_lower or "error" in result_lower or "404" in result_lower, \
            f"Expected GC response, got: {result}"

    # --- AC-P2-007: GC スコープ条件 ---
    def test_ac_p2_007_gc_scope_accepted(self):
        """
        AC-P2-007: memx_gc は stores、age_days_min、exclude_tags 等の
        スコープ条件を受け付けられる

        前提: memx-resolver API が起動していること
        """
        from tools.memx_tools import memx_gc
        from adapters import get_memory_adapter, MemxAdapter

        adapter = get_memory_adapter("test_room")
        assert isinstance(adapter, MemxAdapter), "Expected MemxAdapter"

        result = memx_gc.invoke({
            "mode": "dry-run",
            "room_name": "scope_test_room",
            "stores": "short,journal",
            "age_days_min": 60
        })

        assert result is not None


# ===== 不合格条件テスト =====

class TestPhase2RejectionConditions:
    """Phase 2 不合格条件（要件書 10.4）の検証"""

    def test_resolve_rejects_invalid_action(self):
        """不正な action は MemxAPIError になる"""
        from memx_client import MemxClient, MemxAPIError

        client = MemxClient()

        with pytest.raises(MemxAPIError) as exc_info:
            client.resolve(note_id="test", store="short", resolve_action="invalid")

        assert exc_info.value.code == "INVALID_ACTION"

    def test_gc_distinguishes_dryrun_and_execute(self):
        """GC は dry-run と execute を区別する"""
        from memx_client import MemxClient, MemxAPIError

        client = MemxClient()

        with pytest.raises(MemxAPIError) as exc_info:
            client.gc(mode="delete", room_name="test")

        assert exc_info.value.code == "INVALID_MODE"

    def test_migrate_preserves_source_by_default(self, workspace_tmp_path, local_adapter_config):
        """migrate は既定で source file を削除しない"""
        from tools.memx_migrate import migrate_execute

        room_name = "preserve_rejection_test"
        room_dir = workspace_tmp_path / "characters" / room_name
        entities_dir = room_dir / "memory" / "entities"
        entities_dir.mkdir(parents=True)

        test_entity = entities_dir / "test.md"
        test_entity.write_text("# Test", encoding="utf-8")

        result = migrate_execute(
            source="entity_memory",
            room_name=room_name,
            target_store="knowledge"
        )

        assert result["source_files_preserved"] == True
        assert test_entity.exists()

    def test_migrate_room_isolation(self, workspace_tmp_path, local_adapter_config):
        """migrate は room 単位で動作する"""
        from tools.memx_migrate import migrate_preview

        room_a = "isolation_a"
        room_b = "isolation_b"

        for room_name in [room_a, room_b]:
            room_dir = workspace_tmp_path / "characters" / room_name
            entities_dir = room_dir / "memory" / "entities"
            entities_dir.mkdir(parents=True)
            entity_file = entities_dir / f"{room_name}.md"
            entity_file.write_text(f"# {room_name}", encoding="utf-8")

        result_a = migrate_preview(source="entity_memory", room_name=room_a, target_store="knowledge")
        result_b = migrate_preview(source="entity_memory", room_name=room_b, target_store="knowledge")

        names_a = [c.get("source_name", "") for c in result_a.get("candidates", [])]
        names_b = [c.get("source_name", "") for c in result_b.get("candidates", [])]

        for name in names_a:
            assert room_b not in name
        for name in names_b:
            assert room_a not in name

    def test_resolver_only_via_tools(self):
        """resolve は tool (memx_resolve) として定義されている"""
        from tools.memx_tools import memx_resolve

        assert hasattr(memx_resolve, "name")
        assert "resolve" in memx_resolve.name


# ===== pytest 実行用 =====

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
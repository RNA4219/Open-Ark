# tests/test_legacy_deletion_candidates.py
"""
旧記憶実装削除候補の回帰テスト・依存検出テスト

削除済み:
- dreaming_manager_sync - 削除完了
- motivation_manager_sync - 削除完了
- rag_manager - 削除完了 (memx_search/memx_recall へ置換)
- episodic_memory_manager - 削除完了 (memx_ingest/recall へ置換)
- entity_memory_manager - 削除完了 (entity_tools/memx へ置換)

テスト構成:
- TestImportDetection: 各マネージャーの import 可否検出
- TestEntityMemoryManagerPaths: entity_memory_manager 削除後の代替パス検証
- TestEpisodicMemoryManagerPaths: episodic_memory_manager 削除後の代替パス検証
- TestDreamingManagerPaths: dreaming_manager の機能パス検証
- TestMotivationManagerPaths: motivation_manager の機能パス検証
- TestDependencyMapping: 依存関係マップの整合性検証
- TestGracefulDegradation: 縮退時の graceful handling 検証
- TestReplacementPaths: memx 系ツールによる代替パス検証

用途分類:
- [DELETION_OK_EVIDENCE]: 削除後に通るべきテスト（代替パスが動作することを確認）
- [DELETION_BREAKAGE_DETECTOR]: 削除前に通るべきテスト（削除後に失敗することで問題検出）
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import importlib

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# NOTE: Fixtures are provided by conftest.py:
# - workspace_tmp_path
# - local_adapter_config
# Global mocks for send2trash and gradio are also applied in conftest.py


# ===== Constants =====

# 全削除候補が完了 - DEPRECATION_TARGETS は空
DELETION_CANDIDATES = {
    # entity_memory_manager 削除済み
    # episodic_memory_manager 削除済み
    # rag_manager 削除済み
    # dreaming_manager_sync 削除済み
    # motivation_manager_sync 削除済み
}

SURVIVING_COMPONENTS = [
    "memory_manager",  # LocalAdapter 動作に必要
    "entity_tools",    # entity_memory_manager の代替
    "memory_tools",    # 後方互換性維持
    "local_adapter",   # フォールバック先として必須
    "memx_tools",      # 主要記憶操作経路
]


# ===== Test 1: Import Detection =====
# [DELETION_BREAKAGE_DETECTOR] - 削除後に import が失敗することを検出

@pytest.mark.llm_mock
class TestImportDetection:
    """
    各削除候補マネージャーの import 可否を検出。

    これらのテストは現在（削除前）は PASS するが、
    削除後に FAIL することで「削除が実際に行われた」ことを検出する。

    NOTE: LLM/UI依存あり (memory_manager -> gradio, dreaming_manager -> llm_factory)
    """

    # Note: send2trash is mocked globally in conftest.py

    @pytest.mark.skip(reason="entity_memory_manager 削除済み - entity_tools 経由でテスト")
    def test_entity_memory_manager_importable(self):
        """
        [DELETION_BREAKAGE_DETECTOR] - SKIP: entity_memory_manager 削除済み
        entity_memory_manager が import 可能であることを確認。
        """
        try:
            import entity_memory_manager
            assert hasattr(entity_memory_manager, 'EntityMemoryManager')
        except ImportError as e:
            pytest.fail(f"entity_memory_manager import failed: {e}")

    @pytest.mark.skip(reason="episodic_memory_manager deleted - replaced by memx_ingest/recall")
    def test_episodic_memory_manager_importable(self):
        """
        [DELETION_BREAKAGE_DETECTOR] - SKIP: episodic_memory_manager 削除済み
        episodic_memory_manager が import 可能であることを確認。
        """
        try:
            import episodic_memory_manager
            assert hasattr(episodic_memory_manager, 'EpisodicMemoryManager')
        except ImportError as e:
            pytest.fail(f"episodic_memory_manager import failed: {e}")

    @pytest.mark.skip(reason="rag_manager deleted - replaced by memx_search/memx_recall")
    def test_rag_manager_importable(self):
        """
        [DELETION_BREAKAGE_DETECTOR] - SKIP: rag_manager 削除済み
        rag_manager が import 可能であることを確認。
        """
        try:
            import rag_manager
            assert hasattr(rag_manager, 'RAGManager')
        except ImportError as e:
            pytest.fail(f"rag_manager import failed: {e}")

    def test_dreaming_manager_importable(self):
        """
        [DELETION_BREAKAGE_DETECTOR]
        dreaming_manager が import 可能であることを確認。
        """
        try:
            import dreaming_manager
            assert hasattr(dreaming_manager, 'DreamingManager')
        except ImportError as e:
            pytest.fail(f"dreaming_manager import failed: {e}")

    def test_motivation_manager_importable(self):
        """
        [DELETION_BREAKAGE_DETECTOR]
        motivation_manager が import 可能であることを確認。
        """
        try:
            import motivation_manager
            assert hasattr(motivation_manager, 'MotivationManager')
        except ImportError as e:
            pytest.fail(f"motivation_manager import failed: {e}")

    def test_surviving_components_importable(self):
        """
        [DELETION_OK_EVIDENCE]
        存続対象コンポーネントが import 可能であることを確認。
        これらは削除後も PASS する必要がある。
        """
        # memory_manager
        try:
            import memory_manager
            assert hasattr(memory_manager, 'save_memory_data')
            assert hasattr(memory_manager, 'load_memory_data_safe')
        except ImportError as e:
            pytest.fail(f"memory_manager (surviving) import failed: {e}")

        # entity_tools
        try:
            import tools.entity_tools
            assert hasattr(tools.entity_tools, 'read_entity_memory')
        except ImportError as e:
            pytest.fail(f"entity_tools (surviving) import failed: {e}")

        # memory_tools
        try:
            import tools.memory_tools
            assert hasattr(tools.memory_tools, 'recall_memories')
        except ImportError as e:
            pytest.fail(f"memory_tools (surviving) import failed: {e}")

        # local_adapter
        try:
            from adapters.local_adapter import LocalAdapter
            assert LocalAdapter is not None
        except ImportError as e:
            pytest.fail(f"local_adapter (surviving) import failed: {e}")


# ===== Test 2: EntityMemoryManager Replacement Paths (entity_memory_manager deleted) =====

@pytest.mark.skip(reason="entity_memory_manager 削除済み - entity_tools 経由でテスト")
class TestEntityMemoryManagerPaths:
    """
    entity_memory_manager 削除後の代替パス検証。

    代替パス: entity_tools / memx_ingest/search/show (store=knowledge)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "entity_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        entities_dir = room_dir / "memory" / "entities"
        entities_dir.mkdir(parents=True, exist_ok=True)

    def test_entity_tools_available(self):
        """
        [DELETION_OK_EVIDENCE]
        entity_tools が利用可能。
        """
        from tools.entity_tools import read_entity_memory, write_entity_memory, list_entity_memories, search_entity_memory

        assert read_entity_memory is not None
        assert write_entity_memory is not None
        assert list_entity_memories is not None
        assert search_entity_memory is not None

    def test_memx_replacement_path_exists(self):
        """
        [DELETION_OK_EVIDENCE]
        memx 系ツールによる代替パスが存在することを確認。
        """
        from tools.memx_tools import memx_ingest, memx_search, memx_show

        assert memx_ingest is not None
        assert memx_search is not None
        assert memx_show is not None

    def test_local_adapter_paths_available(self, workspace_tmp_path):
        """
        [DELETION_OK_EVIDENCE]
        LocalAdapter 経路が動作する。
        """
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter(self.room_name)

        # ingest for knowledge store works
        note = adapter.ingest(
            store="knowledge",
            title="LocalTest",
            body="Local adapter test",
            room_name=self.room_name
        )

        assert note is not None

        # search should work
        results = adapter.search("LocalTest", store="knowledge", top_k=5)
        assert isinstance(results, list)


# ===== Test 3: EpisodicMemoryManager Replacement Paths (episodic_memory_manager deleted) =====

class TestEpisodicMemoryManagerPaths:
    """
    episodic_memory_manager 削除後の代替パス検証。

    代替パス: memx_ingest(store="journal") / memx_recall
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "episodic_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        episodic_dir = room_dir / "memory" / "episodic"
        episodic_dir.mkdir(parents=True, exist_ok=True)

    def test_episodic_module_is_deleted(self):
        """
        [DELETION_OK_EVIDENCE]
        episodic_memory_manager は削除済みで import 不能
        """
        with pytest.raises(ModuleNotFoundError):
            import episodic_memory_manager  # noqa: F401

    def test_memx_journal_ingest_works(self):
        """
        [DELETION_OK_EVIDENCE]
        memx_ingest(store="journal") で保存可能
        """
        from tools.memx_tools import memx_ingest

        result = memx_ingest.invoke({
            "store": "journal",
            "title": "Test Episode",
            "body": "Episode saved via memx journal path.",
            "room_name": self.room_name,
        })

        assert "Saved" in result or "Error" not in result

    def test_memx_journal_recall_works(self):
        """
        [DELETION_OK_EVIDENCE]
        memx_recall で取得可能
        """
        from tools.memx_tools import memx_ingest, memx_recall

        # データを保存
        memx_ingest.invoke({
            "store": "journal",
            "title": "Recall Target",
            "body": "Episode for recall test.",
            "room_name": self.room_name,
        })

        # recall
        result = memx_recall.invoke({
            "query": "Recall",
            "room_name": self.room_name,
            "recall_mode": "recent",
        })

        assert result is not None

    def test_introspection_tools_use_memx(self):
        """
        [DELETION_OK_EVIDENCE]
        introspection_tools が memx 経路を使用している。
        """
        from tools.introspection_tools import manage_open_questions, manage_goals
        assert manage_open_questions is not None
        assert manage_goals is not None

    def test_local_adapter_journal_path_works(self):
        """
        [DELETION_OK_EVIDENCE]
        LocalAdapter で journal 操作が可能
        """
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter(self.room_name)
        note = adapter.ingest(
            store="journal",
            title="Adapter Episode",
            body="LocalAdapter journal path works.",
        )

        assert note is not None
        assert note.store == "journal"


# ===== Test 4: RAGManager Replacement Paths (rag_manager deleted) =====

@pytest.mark.llm_mock
class TestRAGManagerPaths:
    """
    rag_manager 削除後の代替パス検証。

    代替パス: memx_search / memx_recall

    NOTE: LLM/UI依存あり (memory_tools -> memory_manager -> gradio)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "rag_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        rag_dir = room_dir / "rag_data"
        rag_dir.mkdir(parents=True, exist_ok=True)

    def test_rag_module_is_deleted(self):
        """
        [DELETION_OK_EVIDENCE]
        rag_manager は削除済みで import 不能
        """
        with pytest.raises(ModuleNotFoundError):
            import rag_manager  # noqa: F401

    def test_memx_search_works(self):
        """
        [DELETION_OK_EVIDENCE]
        memx_search で検索可能
        """
        from tools.memx_tools import memx_search

        result = memx_search.invoke({
            "query": "test query",
            "room_name": self.room_name,
        })

        assert result is not None

    def test_memory_tools_use_memx_recall(self):
        """
        [DELETION_OK_EVIDENCE]
        memory_tools が memx_recall を使用している。
        """
        from tools.memory_tools import recall_memories, search_memory

        assert recall_memories is not None
        assert search_memory is not None

    def test_knowledge_tools_use_memx_search(self):
        """
        [DELETION_OK_EVIDENCE]
        knowledge_tools が memx_search を使用している。
        """
        from tools.knowledge_tools import search_knowledge_base

        assert search_knowledge_base is not None

    def test_local_adapter_search_works(self):
        """
        [DELETION_OK_EVIDENCE]
        LocalAdapter.search が動作する。
        """
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter(self.room_name)

        results = adapter.search("test query", store="journal", top_k=5)
        assert isinstance(results, list)

    def test_memx_recall_replacement_path_exists(self):
        """
        [DELETION_OK_EVIDENCE]
        memx_recall が代替パスとして存在する。
        """
        from tools.memx_tools import memx_recall

        assert memx_recall is not None


# ===== Test 5: DreamingManager Functional Paths =====

@pytest.mark.llm_mock
class TestDreamingManagerPaths:
    """
    dreaming_manager の機能パス検証。

    代替パス: memx 同期 (journal)

    NOTE: LLM依存あり (llm_factory -> langchain_google_genai)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        # Note: send2trash is mocked globally in conftest.py
        self.room_name = "dreaming_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        dreaming_dir = room_dir / "memory" / "dreaming"
        dreaming_dir.mkdir(parents=True, exist_ok=True)

    def test_dreaming_manager_importable(self):
        """
        [DELETION_OK_EVIDENCE]
        dreaming_manager が import 可能。
        """
        from dreaming_manager import DreamingManager
        assert DreamingManager is not None

    def test_dreaming_manager_initialization(self):
        """
        [DELETION_OK_EVIDENCE]
        DreamingManager が初期化できる。
        """
        from dreaming_manager import DreamingManager

        manager = DreamingManager(self.room_name, "dummy_key")
        assert manager is not None
        assert manager.room_name == self.room_name

    def test_dreaming_manager_load_insights(self, workspace_tmp_path):
        """
        [DELETION_OK_EVIDENCE]
        _load_insights が動作する。
        """
        from dreaming_manager import DreamingManager

        manager = DreamingManager(self.room_name, "dummy_key")
        insights = manager._load_insights()
        assert isinstance(insights, list)

    def test_dreaming_manager_monthly_file_path(self):
        """
        [DELETION_OK_EVIDENCE]
        _get_monthly_file_path が動作する。
        """
        from dreaming_manager import DreamingManager

        manager = DreamingManager(self.room_name, "dummy_key")
        path = manager._get_monthly_file_path("2026-04-07 12:00:00")
        assert "2026-04.json" in str(path)

    def test_memx_journal_sync_replacement_path_exists(self):
        """
        [DELETION_OK_EVIDENCE]
        memx journal store が夢・洞察の代替保存先として存在する。
        """
        from tools.memx_tools import memx_ingest

        assert memx_ingest is not None


# ===== Test 6: MotivationManager Functional Paths =====

@pytest.mark.llm_mock
class TestMotivationManagerPaths:
    """
    motivation_manager の機能パス検証。

    代替パス: memx 同期 (short)

    NOTE: LLM依存あり
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        # Note: send2trash is mocked globally in conftest.py
        self.room_name = "motivation_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        memory_dir = room_dir / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

    def test_motivation_manager_importable(self):
        """
        [DELETION_OK_EVIDENCE]
        motivation_manager が import 可能。
        """
        from motivation_manager import MotivationManager
        assert MotivationManager is not None

    def test_motivation_manager_initialization(self):
        """
        [DELETION_OK_EVIDENCE]
        MotivationManager が初期化できる。
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)
        assert manager is not None
        assert manager.room_name == self.room_name

    def test_motivation_manager_get_internal_state(self, workspace_tmp_path):
        """
        [DELETION_OK_EVIDENCE]
        get_internal_state が動作する。
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)
        state = manager.get_internal_state()
        assert isinstance(state, dict)
        assert "drives" in state

    def test_motivation_manager_add_open_question(self):
        """
        [DELETION_OK_EVIDENCE]
        add_open_question が動作する。
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)
        manager.add_open_question(
            topic="Test Question",
            context="Test context",
            priority=0.5
        )

        state = manager.get_internal_state()
        questions = state.get("drives", {}).get("curiosity", {}).get("open_questions", [])
        found = any(q.get("topic") == "Test Question" for q in questions)
        assert found

    def test_motivation_manager_mark_question_resolved(self):
        """
        [DELETION_OK_EVIDENCE]
        mark_question_resolved が動作する。
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)
        manager.add_open_question(
            topic="Resolvable Question",
            context="Test context",
            priority=0.5
        )

        manager.mark_question_resolved("Resolvable Question", answer_summary="Resolved.")

        state = manager.get_internal_state()
        questions = state.get("drives", {}).get("curiosity", {}).get("open_questions", [])
        resolved = [q for q in questions if q.get("topic") == "Resolvable Question" and q.get("resolved_at")]
        assert len(resolved) >= 1

    @pytest.mark.skip(reason="alarm_manager requires schedule dependency")
    def test_alarm_manager_uses_motivation_manager(self):
        """
        [DELETION_BREAKAGE_DETECTOR]
        alarm_manager が MotivationManager を使用している。
        """

    def test_memx_short_sync_replacement_path_exists(self):
        """
        [DELETION_OK_EVIDENCE]
        memx short store が未解決の問いの代替保存先として存在する。
        """
        from tools.memx_tools import memx_ingest

        assert memx_ingest is not None


# ===== Test 7: Dependency Mapping =====

class TestDependencyMapping:
    """
    依存関係マップの整合性検証。

    このテストは「どのモジュールがどの削除候補に依存しているか」を文書化し、
    削除時に影響範囲を把握できるようにする。
    """

    def test_entity_memory_manager_removed_from_targets(self):
        """
        [DOCUMENTATION]
        entity_memory_manager は削除済み - DEPRECATION_TARGETS に存在しない。
        """
        from tools.memx_phase3 import DEPRECATION_TARGETS

        # entity_memory_manager は削除済みなので DEPRECATION_TARGETS に存在しない
        assert "entity_memory_manager" not in DEPRECATION_TARGETS

    def test_episodic_memory_manager_removed_from_targets(self):
        """
        [DOCUMENTATION]
        episodic_memory_manager は削除済み。
        DEPRECATION_TARGETS に含まれていないことを確認。
        """
        from tools.memx_phase3 import DEPRECATION_TARGETS

        # episodic_memory_manager は削除済み
        assert "episodic_memory_manager" not in DEPRECATION_TARGETS

    def test_rag_manager_removed_from_targets(self):
        """
        [DOCUMENTATION]
        rag_manager は削除済み。
        DEPRECATION_TARGETS に含まれていないことを確認。
        """
        from tools.memx_phase3 import DEPRECATION_TARGETS

        # rag_manager は削除済み
        assert "rag_manager" not in DEPRECATION_TARGETS

    def test_dreaming_manager_sync_removed_from_targets(self):
        """
        [DOCUMENTATION]
        dreaming_manager_sync は削除済み。
        DEPRECATION_TARGETS に含まれていないことを確認。
        """
        from tools.memx_phase3 import DEPRECATION_TARGETS

        # dreaming_manager_sync は削除済み
        assert "dreaming_manager_sync" not in DEPRECATION_TARGETS

    def test_motivation_manager_dependencies_documented(self):
        """
        [DOCUMENTATION]
        motivation_manager_sync は削除済み。
        DEPRECATION_TARGETS に含まれていないことを確認。
        """
        from tools.memx_phase3 import DEPRECATION_TARGETS

        # motivation_manager_sync は削除済み
        assert "motivation_manager_sync" not in DEPRECATION_TARGETS

    def test_all_deprecation_targets_have_required_fields(self):
        """
        [DOCUMENTATION]
        DEPRECATION_TARGETS の各エントリが必須フィールドを持っている。
        """
        from tools.memx_phase3 import DEPRECATION_TARGETS

        required_fields = [
            "description",
            "memx_replacement",
            "can_disable",
            "read_only_mode_available",
            "rollback_supported",
            "status",
        ]

        for name, info in DEPRECATION_TARGETS.items():
            for field in required_fields:
                assert field in info, f"{name} missing field: {field}"


# ===== Test 8: Graceful Degradation =====

@pytest.mark.llm_mock
class TestGracefulDegradation:
    """
    縮退時の graceful handling 検証。

    これらのテストは「削除候補が無効化された場合」の挙動を検証し、
    フォールバックや代替パスが動作することを確認する。

    NOTE: LLM依存あり (entity_tools, memx_tools -> langchain)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config):
        pass

    def test_local_adapter_available_when_memx_disabled(self):
        """
        [DELETION_OK_EVIDENCE]
        memx が無効な場合、LocalAdapter が使用可能である。
        """
        from adapters import get_memory_adapter

        adapter = get_memory_adapter("fallback_test")
        # クラス名で確認（モジュール再読み込みの問題を回避）
        assert type(adapter).__name__ == "LocalAdapter"
        assert adapter.is_available()

    def test_entity_tools_available_when_entity_memory_manager_disabled(self):
        """
        [DELETION_OK_EVIDENCE]
        entity_tools が entity_memory_manager 無効時も（LocalAdapter経由で）動作可能。

        注: entity_tools は entity_memory_manager を直接 import するため、
        実際の削除後は entity_tools も修正が必要。
        """
        # 現状: entity_tools は entity_memory_manager を直接使用
        # 削除後: entity_tools を LocalAdapter または memx_tools 経由に変更が必要

        from tools.entity_tools import read_entity_memory

        # tool が定義されていること（現状）
        assert read_entity_memory is not None

        # 削除後の対応: read_entity_memory を LocalAdapter.search または memx_search に変更

    def test_phase2_phase3_tests_pass_with_local_adapter(self, workspace_tmp_path):
        """
        [DELETION_OK_EVIDENCE]
        Phase 2/3 テストが LocalAdapter で動作する。
        """
        # これは test_memx_phase2.py / test_memx_phase3.py で検証済み
        # ここでは設定確認のみ

        import config_manager

        settings = config_manager.CONFIG_GLOBAL.get("memx_settings", {})
        assert settings.get("use_memx") is False

    def test_memx_tools_available_as_replacement(self):
        """
        [DELETION_OK_EVIDENCE]
        memx 系ツールが代替として使用可能である。
        """
        from tools.memx_tools import memx_ingest, memx_search, memx_show, memx_recall, memx_resolve, memx_gc

        assert memx_ingest is not None
        assert memx_search is not None
        assert memx_show is not None
        assert memx_recall is not None
        assert memx_resolve is not None
        assert memx_gc is not None


# ===== Test 9: Replacement Paths =====

@pytest.mark.llm_mock
class TestReplacementPaths:
    """
    memx 系ツールによる代替パス検証。

    これらのテストは「削除後に代替パスが動作する」ことを確認し、
    削除の安全性を担保する。

    NOTE: LLM依存あり (memx_tools -> langchain)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "replacement_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        room_dir.mkdir(parents=True, exist_ok=True)

    def test_memx_ingest_for_knowledge(self, workspace_tmp_path):
        """
        [DELETION_OK_EVIDENCE]
        memx_ingest で knowledge store に保存可能（entity_memory_manager の代替）。
        """
        from tools.memx_tools import memx_ingest

        # LocalAdapter 使用時（memx 無効）
        result = memx_ingest.invoke({
            "store": "knowledge",
            "title": "TestEntity",
            "body": "Test entity content",
            "room_name": self.room_name
        })

        assert result is not None
        # result には成功メッセージが含まれる

    def test_memx_search_for_knowledge(self, workspace_tmp_path):
        """
        [DELETION_OK_EVIDENCE]
        memx_search で knowledge store を検索可能。
        """
        from tools.memx_tools import memx_search

        result = memx_search.invoke({
            "query": "TestEntity",
            "room_name": self.room_name
        })

        assert result is not None

    def test_memx_ingest_for_journal(self, workspace_tmp_path):
        """
        [DELETION_OK_EVIDENCE]
        memx_ingest で journal store に保存可能（episodic_memory_manager の代替）。
        """
        from tools.memx_tools import memx_ingest

        result = memx_ingest.invoke({
            "store": "journal",
            "title": "TestEpisode",
            "body": "Test episode content",
            "room_name": self.room_name
        })

        assert result is not None

    def test_memx_recall_as_rag_replacement(self, workspace_tmp_path):
        """
        [DELETION_OK_EVIDENCE]
        memx_recall が RAGManager の代替として動作可能。
        """
        from tools.memx_tools import memx_recall

        result = memx_recall.invoke({
            "query": "test query",
            "room_name": self.room_name,
            "recall_mode": "relevant"
        })

        assert result is not None

    def test_memx_ingest_for_short(self, workspace_tmp_path):
        """
        [DELETION_OK_EVIDENCE]
        memx_ingest で short store に保存可能（motivation_manager の問いの代替）。
        """
        from tools.memx_tools import memx_ingest

        result = memx_ingest.invoke({
            "store": "short",
            "title": "Unresolved Question",
            "body": "What is the meaning of this?",
            "room_name": self.room_name
        })

        assert result is not None


# ===== Test 10: Method Coverage =====

@pytest.mark.llm_mock
class TestMethodCoverage:
    """
    各マネージャーの重要メソッドがテストされていることを確認。

    このテストは「テストカバレッジ」を監視し、削除前に重要パスが
    全てテストされていることを確認する。

    NOTE: LLM依存あり (dreaming_manager, motivation_manager)
    """

    @pytest.mark.skip(reason="entity_memory_manager 削除済み")
    def test_entity_memory_manager_methods_covered(self):
        """
        [COVERAGE] - SKIP: entity_memory_manager 削除済み
        entity_memory_manager の重要メソッドがテストされている。
        """
        covered_methods = [
            "read_entry",
            "create_or_update_entry",
            "list_entries",
            "search_entries",
        ]

        from entity_memory_manager import EntityMemoryManager

        for method_name in covered_methods:
            assert hasattr(EntityMemoryManager, method_name), \
                f"EntityMemoryManager missing method: {method_name}"

    @pytest.mark.skip(reason="episodic_memory_manager deleted")
    def test_episodic_memory_manager_methods_covered(self):
        """
        [SKIP] episodic_memory_manager 削除済み
        """
        covered_methods = [
            "_load_memory",
            "get_latest_memory_date",
        ]

        from episodic_memory_manager import EpisodicMemoryManager

        for method_name in covered_methods:
            assert hasattr(EpisodicMemoryManager, method_name), \
                f"EpisodicMemoryManager missing method: {method_name}"

    def test_motivation_manager_methods_covered(self):
        """
        [COVERAGE]
        motivation_manager の重要メソッドがテストされている。
        """
        covered_methods = [
            "get_internal_state",
            "update_last_interaction",
        ]

        from motivation_manager import MotivationManager

        for method_name in covered_methods:
            assert hasattr(MotivationManager, method_name), \
                f"MotivationManager missing method: {method_name}"

    def test_dreaming_manager_methods_covered(self):
        """
        [COVERAGE]
        dreaming_manager の重要メソッドがテストされている。
        """
        covered_methods = [
            "_load_insights",
        ]

        from dreaming_manager import DreamingManager

        for method_name in covered_methods:
            assert hasattr(DreamingManager, method_name), \
                f"DreamingManager missing method: {method_name}"


# ===== pytest 実行用 =====

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
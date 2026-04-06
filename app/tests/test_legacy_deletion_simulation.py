# tests/test_legacy_deletion_simulation.py
"""
旧記憶実装 削除候補 削除シミュレーションテスト

MEMX_LEGACY_DELETION_CONTRACTS.md に定義された削除可条件に基づき、
import 欠落や直接依存が残っている場合の検知を行う。

削除可条件:
- import 欠落シミュレーションでも致命障害にならない
- 想定外の直接 import が残っていれば失敗する

目的:
このテストは「テストを緑にすること」ではなく
「削除時の依存残りを本当に検出できること」を目的とする。
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import importlib
import builtins

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# NOTE: Fixtures are provided by conftest.py:
# - workspace_tmp_path
# - local_adapter_config
# Global mocks for send2trash and gradio are also applied in conftest.py


# ===== import 欠落シミュレーション =====

class ImportBlocker:
    """
    指定されたモジュールの import を一時的に失敗させるコンテキストマネージャ。

    builtins.__import__ をフックし、指定モジュール名で ModuleNotFoundError を発生させる。
    さらに sys.modules から該当モジュールを削除して、再importを強制する。

    使用例:
        with ImportBlocker("entity_memory_manager"):
            # この中では entity_memory_manager の import が失敗する
            import entity_memory_manager  # -> ModuleNotFoundError
    """

    def __init__(self, blocked_module: str):
        self.blocked_module = blocked_module
        self.original_import = None
        self.removed_modules = []

    def _should_block(self, name: str) -> bool:
        """ブロックすべきモジュール名かどうかを判定"""
        if name == self.blocked_module:
            return True
        if name.startswith(self.blocked_module + "."):
            return True
        return False

    def _blocked_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """ブロック用の __import__ フック"""
        if self._should_block(name):
            raise ModuleNotFoundError(
                f"Simulated deletion: module '{name}' has been removed",
                name=name
            )
        return self.original_import(name, globals, locals, fromlist, level)

    def __enter__(self):
        # builtins.__import__ を保存してフックを設定
        self.original_import = builtins.__import__
        builtins.__import__ = self._blocked_import

        # sys.modules から該当モジュールを削除（再importを強制）
        modules_to_remove = [
            key for key in list(sys.modules.keys())
            if key == self.blocked_module or key.startswith(self.blocked_module + ".")
        ]
        for key in modules_to_remove:
            self.removed_modules.append((key, sys.modules.pop(key, None)))

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # フックを解除
        builtins.__import__ = self.original_import

        # 削除したモジュールを復元
        for key, module in self.removed_modules:
            if module is not None:
                sys.modules[key] = module

        return False


def block_import(module_name: str):
    """
    指定モジュールの import をブロックするコンテキストマネージャを返す。

    使用例:
        with block_import("entity_memory_manager"):
            import entity_memory_manager  # -> ModuleNotFoundError
    """
    return ImportBlocker(module_name)


# ===== シミュレーション機能自体のテスト =====

@pytest.mark.deletion_simulation
class TestImportBlockerFunctionality:
    """
    ImportBlocker が正しく動作することを確認するテスト。
    """

    def test_blocker_raises_module_not_found_error(self):
        """
        ImportBlocker が ModuleNotFoundError を発生させることを確認。
        """
        with block_import("nonexistent_test_module"):
            with pytest.raises(ModuleNotFoundError) as exc_info:
                import nonexistent_test_module

            assert "nonexistent_test_module" in str(exc_info.value)

    def test_blocker_works_for_submodules(self):
        """
        サブモジュールもブロックされることを確認。
        """
        with block_import("nonexistent_package"):
            with pytest.raises(ModuleNotFoundError) as exc_info:
                import nonexistent_package.submodule

            assert "nonexistent_package" in str(exc_info.value)

    def test_blocker_allows_other_imports(self):
        """
        ブロック対象外の import は成功することを確認。
        """
        with block_import("nonexistent_test_module"):
            # os は通常 import 可能
            import os
            assert os is not None

    def test_blocker_restores_after_exit(self):
        """
        コンテキスト終了後に import が復旧することを確認。
        """
        # 先にブロックしない状態で import 可能
        import json
        assert json is not None

        # ブロック中は失敗
        with block_import("json"):
            with pytest.raises(ModuleNotFoundError):
                import json

        # ブロック終了後は復旧
        import json
        assert json is not None


# ===== entity_memory_manager 削除シミュレーション (entity_memory_manager 削除済み) =====

@pytest.mark.deletion_simulation
class TestEntityMemoryManagerDeletionSimulation:
    """
    entity_memory_manager 削除後の代替パス検証。

    削除済み: entity_memory_manager は entity_tools / memx 経路に置換
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "entity_deletion_sim"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        entities_dir = room_dir / "memory" / "entities"
        entities_dir.mkdir(parents=True, exist_ok=True)

    def test_entity_module_is_deleted(self):
        """
        検証: entity_memory_manager は削除済みで import 不能
        """
        with pytest.raises(ModuleNotFoundError):
            import entity_memory_manager  # noqa: F401

    def test_entity_tools_available_as_replacement(self):
        """
        検証: entity_tools が代替として利用可能
        """
        from tools.entity_tools import (
            write_entity_memory,
            read_entity_memory,
            list_entity_memories,
            search_entity_memory,
        )

        write_entity_memory.invoke({
            "entity_name": "Replacement Entity",
            "content": "Replacement path is active.",
            "room_name": self.room_name,
            "append": False,
        })
        read_result = read_entity_memory.invoke({
            "entity_name": "Replacement Entity",
            "room_name": self.room_name,
        })
        listing = list_entity_memories.invoke({"room_name": self.room_name})
        search_result = search_entity_memory.invoke({
            "query": "Replacement",
            "room_name": self.room_name,
        })

        assert "Replacement path is active." in read_result
        assert "Replacement Entity" in listing
        assert "Replacement Entity" in search_result

    def test_local_adapter_no_entity_memory_manager_dependency(self):
        """
        検証: LocalAdapter は entity_memory_manager に依存していない（削除済み）
        """
        # LocalAdapter は直接ファイル操作を使用
        from adapters.local_adapter import LocalAdapter
        adapter = LocalAdapter(self.room_name)
        assert adapter is not None
        assert adapter.is_available()

    def test_local_adapter_replacement_paths_work(self):
        """
        検証: LocalAdapter の代替 knowledge 導線が動作する
        """
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter(self.room_name)
        note = adapter.ingest(
            store="knowledge",
            title="Simulated Entity",
            body="LocalAdapter replacement still works.",
        )
        results = adapter.search("Simulated", store="knowledge", top_k=5)
        target = next(r for r in results if r.title == "Simulated Entity")
        shown = adapter.show(target.id, store="knowledge")

        assert any(r.title == "Simulated Entity" for r in results)
        assert shown is not None and "LocalAdapter replacement still works." in shown.body

    @pytest.mark.skip(reason="Documentation test - slow, run manually for full dependency audit")
    def test_entity_direct_import_locations_documented(self):
        """
        文書化: entity_memory_manager を直接 import している既知の場所
        """
        known_importers = [
            "adapters.local_adapter",    # 条件付き import
            "agent.graph",               # 直接 import
            "dreaming_manager",          # 直接 import
            "ui_handlers",               # 直接 import
            "tools.entity_tools",        # 直接 import
            "tools.introspection_tools", # 直接 import（条件付きの可能性）
        ]

        # これらのモジュールが現状 import 可能であることを確認
        for importer in known_importers:
            try:
                # 既に import 済みの場合はスキップ
                if importer in sys.modules:
                    continue
                module = importlib.import_module(importer)
            except ImportError:
                # テスト環境で利用できない場合はスキップ
                pass


# ===== episodic_memory_manager 削除シミュレーション (episodic_memory_manager 削除済み) =====

@pytest.mark.deletion_simulation
class TestEpisodicMemoryManagerDeletionSimulation:
    """
    episodic_memory_manager 削除後の代替パス検証。

    削除済み: episodic_memory_manager は memx journal 経路に置換
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "episode_deletion_sim"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        episodic_dir = room_dir / "memory" / "episodic"
        episodic_dir.mkdir(parents=True, exist_ok=True)

    def test_episode_module_is_deleted(self):
        """
        検証: episodic_memory_manager は削除済みで import 不能
        """
        with pytest.raises(ModuleNotFoundError):
            import episodic_memory_manager  # noqa: F401

    def test_episode_memx_journal_save_works(self):
        """
        検証: memx_ingest(store="journal") でエピソード保存が動作
        """
        from tools.memx_tools import memx_ingest

        result = memx_ingest.invoke({
            "store": "journal",
            "title": "Deletion Sim Episode",
            "body": "Episodes saved through memx journal path.",
            "room_name": self.room_name,
        })

        assert "Saved" in result or "Error" not in result

    def test_episode_memx_recall_works(self):
        """
        検証: memx_recall でエピソード取得が動作
        """
        from tools.memx_tools import memx_ingest, memx_recall

        # データを保存
        memx_ingest.invoke({
            "store": "journal",
            "title": "Recall Test Episode",
            "body": "Test episode for recall verification.",
            "room_name": self.room_name,
        })

        # recall
        result = memx_recall.invoke({
            "query": "Recall Test",
            "room_name": self.room_name,
            "recall_mode": "recent",
        })

        assert result is not None

    def test_episode_local_adapter_journal_works(self):
        """
        検証: LocalAdapter 経由で journal 操作が動作
        """
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter(self.room_name)

        note = adapter.ingest(
            store="journal",
            title="Adapter Episode",
            body="LocalAdapter journal path works after deletion.",
        )

        assert note is not None
        assert note.store == "journal"

    @pytest.mark.skip(reason="introspection_tools requires langchain_core (llm_mock needed for this test)")
    def test_episode_introspection_resolve_creates_episode(self):
        """
        検証: introspection_tools.resolve が journal 経路でエピソード生成
        """

    @pytest.mark.skip(reason="ui_handlers requires gradio dependency")
    def test_ui_handlers_no_episodic_dependency(self):
        """
        検出: ui_handlers から episodic_memory_manager 依存を削除済み
        """


# ===== rag_manager 削除シミュレーション (rag_manager 削除済み) =====

@pytest.mark.deletion_simulation
@pytest.mark.llm_mock
class TestRAGManagerDeletionSimulation:
    """
    rag_manager 削除後の代替パス検証。

    削除済み: rag_manager は memx_search / memx_recall に置換

    NOTE: LLM/UI依存あり (memory_tools -> memory_manager -> gradio)
    """

    @pytest.mark.skip(reason="rag_manager deleted - import blocked test not applicable")
    def test_rag_import_can_be_blocked(self):
        """
        検証: rag_manager の import をブロックできる
        """
        import rag_manager
        assert rag_manager is not None

        with block_import("rag_manager"):
            with pytest.raises(ModuleNotFoundError) as exc_info:
                import rag_manager as blocked

            assert "rag_manager" in str(exc_info.value)

    def test_local_adapter_rag_dependency_removed(self):
        """
        検出: LocalAdapter から rag_manager 依存を削除済み

        LocalAdapter.search は rag_manager を使用しなくなった。
        """
        # rag_manager は削除済みなので import 不可
        with pytest.raises(ModuleNotFoundError):
            import rag_manager

        # LocalAdapter は正常に初期化可能
        from adapters.local_adapter import LocalAdapter
        adapter = LocalAdapter("test_room")
        assert adapter is not None

    def test_memory_tools_rag_dependency_removed(self):
        """
        検出: memory_tools は memx 経路を使用

        memory_tools は rag_manager に依存せず、memx 経路を使用。
        """
        # memory_tools は正常に import 可能
        import tools.memory_tools
        assert tools.memory_tools is not None

    @pytest.mark.skip(reason="rag_manager deleted - documentation test not applicable")
    def test_rag_direct_import_locations_documented(self):
        """
        文書化: rag_manager を直接 import している既知の場所
        """
        known_importers = [
            "adapters.local_adapter",  # 関数内 import
            "alarm_manager",           # 関数内 import
            "dreaming_manager",        # 直接 import
            "nexus_ark",
            "ui_handlers",             # 関数内 import
            "tools.knowledge_tools",   # 関数内 import
            "tools.memory_tools",      # 関数内 import
        ]

        for importer in known_importers:
            try:
                if importer in sys.modules:
                    continue
                importlib.import_module(importer)
            except ImportError:
                pass


# ===== dreaming_manager 削除シミュレーション =====

@pytest.mark.deletion_simulation
@pytest.mark.llm_mock
class TestDreamingManagerDeletionSimulation:
    """
    dreaming_manager の正常系テスト。

    NOTE: LLM依存あり (llm_factory -> langchain_google_genai)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        # Note: send2trash is mocked globally in conftest.py
        self.room_name = "dream_deletion_sim"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        dreaming_dir = room_dir / "memory" / "dreaming"
        dreaming_dir.mkdir(parents=True, exist_ok=True)

    def test_dream_manager_importable(self):
        """
        検証: dreaming_manager が import 可能
        """
        import dreaming_manager
        assert dreaming_manager is not None

    def test_dream_manager_initialization(self):
        """
        検証: DreamingManager が初期化できる
        """
        from dreaming_manager import DreamingManager

        manager = DreamingManager(self.room_name, "dummy_key")
        assert manager is not None
        assert manager.room_name == self.room_name

    def test_dream_manager_load_insights(self):
        """
        検証: _load_insights が動作する
        """
        from dreaming_manager import DreamingManager

        manager = DreamingManager(self.room_name, "dummy_key")
        insights = manager._load_insights()
        assert isinstance(insights, list)

    def test_dream_manager_monthly_file_path(self):
        """
        検証: 月次ファイルパスが正しく生成される
        """
        from dreaming_manager import DreamingManager

        manager = DreamingManager(self.room_name, "dummy_key")
        path = manager._get_monthly_file_path("2026-04-07 12:00:00")
        assert "2026-04.json" in str(path)

    @pytest.mark.skip(reason="alarm_manager requires schedule dependency")
    def test_alarm_manager_dreaming_dependency(self):
        """
        検出: alarm_manager は dreaming_manager に依存している
        """
        pass


# ===== motivation_manager 削除シミュレーション =====

@pytest.mark.deletion_simulation
@pytest.mark.llm_mock
class TestMotivationManagerDeletionSimulation:
    """
    motivation_manager の正常系テスト。

    NOTE: LLM依存あり
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        # Note: send2trash is mocked globally in conftest.py
        self.room_name = "motivation_deletion_sim"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        memory_dir = room_dir / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

    def test_motivation_manager_importable(self):
        """
        検証: motivation_manager が import 可能
        """
        import motivation_manager
        assert motivation_manager is not None

    def test_motivation_manager_initialization(self):
        """
        検証: MotivationManager が初期化できる
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)
        assert manager is not None
        assert manager.room_name == self.room_name

    def test_motivation_manager_get_internal_state(self):
        """
        検証: get_internal_state が動作する
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)
        state = manager.get_internal_state()
        assert isinstance(state, dict)
        assert "drives" in state

    def test_motivation_manager_add_open_question(self):
        """
        検証: add_open_question が動作する
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
        検証: mark_question_resolved が動作する
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

    @pytest.mark.skip(reason="ui_handlers requires gradio dependency")
    def test_ui_handlers_motivation_dependency(self):
        """
        検出: ui_handlers は motivation_manager を使用している
        """


# ===== 共通削除シミュレーション =====

@pytest.mark.deletion_simulation
@pytest.mark.llm_mock
class TestCommonDeletionSimulation:
    """
    共通の削除シミュレーションテスト。

    全削除候補が完了したため、代替パスの検証のみ行う。

    NOTE: LLM/UI依存あり (memory_manager -> gradio, entity_tools/memory_tools -> langchain)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config):
        pass

    @pytest.mark.skip(reason="DEPRECATION_TARGETS は空（全候補削除済み）")
    def test_disabled_targets_do_not_break_phase2_acceptance_subset(self):
        """
        共通: disabled 相当でも Phase 2 主要導線が保たれる
        """
        from tools.memx_phase3 import set_deprecation_status

        targets = [
            "entity_memory_manager",
            "episodic_memory_manager",
        ]

        for target in targets:
            set_deprecation_status(target, "disabled")

        try:
            from tools.memx_tools import memx_ingest, memx_search, memx_show
            from tools.memx_tools import memx_recall, memx_resolve, memx_gc

            assert memx_ingest is not None
            assert memx_search is not None
            assert memx_show is not None
            assert memx_recall is not None
            assert memx_resolve is not None
            assert memx_gc is not None

        finally:
            for target in targets:
                set_deprecation_status(target, "active")

    @pytest.mark.skip(reason="DEPRECATION_TARGETS は空（全候補削除済み）")
    def test_disabled_targets_do_not_break_phase3_acceptance_subset(self):
        """
        共通: disabled 相当でも Phase 3 主要導線が保たれる
        """
        from tools.memx_phase3 import (
            set_deprecation_status,
            judge_migration_status,
            get_migration_guide,
        )

        targets = [
            "entity_memory_manager",
            "episodic_memory_manager",
        ]

        for target in targets:
            set_deprecation_status(target, "disabled")

        try:
            judgment = judge_migration_status("test_room")
            assert judgment is not None

            guide = get_migration_guide()
            assert guide is not None

        finally:
            for target in targets:
                set_deprecation_status(target, "active")

    def test_surviving_components_still_handle_fallback(self):
        """
        共通: 存続対象がフォールバック責務を維持する
        """
        try:
            from memory_manager import save_memory_data, load_memory_data_safe
            from tools.entity_tools import read_entity_memory, write_entity_memory
            from tools.memory_tools import recall_memories, search_memory
            from adapters.local_adapter import LocalAdapter

            assert save_memory_data is not None
            assert load_memory_data_safe is not None
            assert read_entity_memory is not None
            assert write_entity_memory is not None
            assert recall_memories is not None
            assert search_memory is not None
            assert LocalAdapter is not None

        except ImportError as e:
            pytest.fail(f"Surviving component import failed: {e}")

    def test_memx_paths_cover_deleted_capabilities(self):
        """
        共通: memx 側代替導線が主要能力をカバーする
        """
        from tools.memx_tools import memx_ingest, memx_search, memx_show, memx_recall, memx_resolve, memx_gc

        assert memx_ingest is not None
        assert memx_search is not None
        assert memx_show is not None
        assert memx_recall is not None
        assert memx_resolve is not None
        assert memx_gc is not None

        assert memx_ingest.__doc__ is not None
        assert memx_search.__doc__ is not None
        assert memx_recall.__doc__ is not None


# ===== pytest 実行用 =====

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "deletion_simulation"])

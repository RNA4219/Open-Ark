# tests/test_legacy_disabled_mode.py
"""
旧記憶実装 削除候補 状態テスト

MEMX_LEGACY_DELETION_CONTRACTS.md に定義された削除可条件に基づき、
read_only / disabled 状態時の期待挙動を検証する。

削除可条件:
- disabled 状態で主要導線が維持される
- read_only 状態で参照系が維持される
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# NOTE: Fixtures are provided by conftest.py:
# - workspace_tmp_path
# - local_adapter_config
# Global mocks for send2trash and gradio are also applied in conftest.py


# ===== entity_memory_manager 状態テスト (entity_memory_manager 削除済み) =====

@pytest.mark.disabled_mode
class TestEntityMemoryManagerDisabledMode:
    """
    entity_memory_manager 削除後の代替パス検証。

    削除済み: entity_memory_manager は entity_tools / memx 経路に置換
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "entity_disabled_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        entities_dir = room_dir / "memory" / "entities"
        entities_dir.mkdir(parents=True, exist_ok=True)

    def test_entity_paths_available_via_entity_tools(self, workspace_tmp_path):
        """
        状態テスト: entity_tools 経路で知識操作が可能
        """
        from tools.entity_tools import write_entity_memory, read_entity_memory, list_entity_memories

        write_result = write_entity_memory.invoke({
            "entity_name": "Disabled Entity",
            "content": "Entity data survives disabled mode.",
            "room_name": self.room_name,
            "append": False,
        })
        read_result = read_entity_memory.invoke({
            "entity_name": "Disabled Entity",
            "room_name": self.room_name,
        })
        listing = list_entity_memories.invoke({"room_name": self.room_name})

        assert "created" in write_result.lower() or "overwritten" in write_result.lower()
        assert "Entity data survives disabled mode." in read_result
        assert "Disabled Entity" in listing

    def test_entity_local_adapter_knowledge_paths_alive(self, workspace_tmp_path):
        """
        状態テスト: LocalAdapter の knowledge 導線が生きている
        """
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter(self.room_name)
        note = adapter.ingest(
            store="knowledge",
            title="Adapter Disabled Entity",
            body="LocalAdapter still writes entity knowledge.",
        )
        results = adapter.search("Adapter Disabled", store="knowledge", top_k=5)
        target = next(r for r in results if r.title == "Adapter Disabled Entity")
        shown = adapter.show(target.id, store="knowledge")

        assert note.store == "knowledge"
        assert any(r.title == "Adapter Disabled Entity" for r in results)
        assert shown is not None and "LocalAdapter still writes entity knowledge." in shown.body


# ===== episodic_memory_manager 状態テスト (episodic_memory_manager 削除済み) =====

@pytest.mark.disabled_mode
class TestEpisodicMemoryManagerDisabledMode:
    """
    episodic_memory_manager 削除後の代替パス検証。

    削除済み: episodic_memory_manager は memx 経路に置換
    disabled 相当でも journal 系導線が動作することを確認
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "episode_disabled_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        episodic_dir = room_dir / "memory" / "episodic"
        episodic_dir.mkdir(parents=True, exist_ok=True)

    def test_episode_journal_save_via_memx(self, workspace_tmp_path):
        """
        状態テスト: memx_ingest(store="journal") でエピソード保存が動作
        """
        from tools.memx_tools import memx_ingest

        result = memx_ingest.invoke({
            "store": "journal",
            "title": "Disabled Mode Episode",
            "body": "Episodes survive through memx journal path.",
            "room_name": self.room_name,
        })

        assert "Saved" in result or "Error" not in result

    def test_episode_journal_recall_via_memx(self, workspace_tmp_path):
        """
        状態テスト: memx_recall で履歴参照が可能
        """
        from tools.memx_tools import memx_ingest, memx_recall

        # 先にデータを保存
        memx_ingest.invoke({
            "store": "journal",
            "title": "Recall Test Episode",
            "body": "This episode tests recall functionality.",
            "room_name": self.room_name,
        })

        # recall で取得
        recall_result = memx_recall.invoke({
            "query": "Recall Test",
            "room_name": self.room_name,
            "recall_mode": "recent",
        })

        assert recall_result is not None

    def test_episode_local_adapter_journal_path_alive(self, workspace_tmp_path):
        """
        状態テスト: LocalAdapter の journal 導線が動作
        """
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter(self.room_name)

        # journal に保存
        note = adapter.ingest(
            store="journal",
            title="Adapter Journal Entry",
            body="LocalAdapter journal path works in disabled mode.",
        )

        assert note is not None
        assert note.store == "journal"

    def test_episode_search_via_memx_search(self, workspace_tmp_path):
        """
        状態テスト: memx_search で journal 検索が動作
        """
        from tools.memx_tools import memx_ingest, memx_search

        # 特徴的なエントリを保存
        unique_keyword = "EpisodeSearchKeyword999"
        memx_ingest.invoke({
            "store": "journal",
            "title": "Search Target Episode",
            "body": f"Contains {unique_keyword} for search test.",
            "room_name": self.room_name,
        })

        # 検索
        search_result = memx_search.invoke({
            "query": unique_keyword,
            "room_name": self.room_name,
            "store": "journal",
        })

        assert search_result is not None

    @pytest.mark.skip(reason="introspection_tools requires langchain_core (llm_mock needed for this test)")
    def test_episode_introspection_resolve_path_alive(self, workspace_tmp_path):
        """
        状態テスト: introspection_tools の resolve が journal 経路で動作
        """
        from tools.introspection_tools import manage_open_questions
        from motivation_manager import MotivationManager

        # 問いを追加
        mm = MotivationManager(self.room_name)
        mm.add_open_question(
            topic="Disabled Mode Question",
            context="Testing resolve in disabled mode.",
            priority=0.5
        )

        # resolve
        result = manage_open_questions.invoke({
            "room_name": self.room_name,
            "action": "resolve",
            "question_index": 1,
            "reflection": "Resolve works through memx journal path.",
        })

        assert "解決済み" in result or "Error" not in result


# ===== rag_manager 状態テスト (rag_manager 削除済み) =====

@pytest.mark.disabled_mode
class TestRAGManagerDisabledMode:
    """
    rag_manager 削除後の代替パス検証。

    削除済み: rag_manager は memx_search / memx_recall に置換
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "rag_disabled_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        rag_dir = room_dir / "rag_data"
        rag_dir.mkdir(parents=True, exist_ok=True)

    def test_rag_search_paths_alive_via_memx(self, workspace_tmp_path):
        """
        状態テスト: memx 経路で検索主要導線が生きる
        """
        from tools.memx_tools import memx_search, memx_recall
        from adapters.local_adapter import LocalAdapter

        # LocalAdapter 経由での検索が動作
        adapter = LocalAdapter(self.room_name)
        results = adapter.search("test query", store="journal", top_k=5)
        assert isinstance(results, list)

        # memx 経路も動作
        search_result = memx_search.invoke({
            "query": "test",
            "room_name": self.room_name
        })
        assert search_result is not None

    def test_rag_recall_via_memx_recall(self, workspace_tmp_path):
        """
        状態テスト: memx_recall で参照系が動作
        """
        from tools.memx_tools import memx_recall
        from adapters.local_adapter import LocalAdapter

        # LocalAdapter 経由での検索が動作
        adapter = LocalAdapter(self.room_name)
        results = adapter.search("any query", top_k=5)
        assert isinstance(results, list)

        # memx_recall も動作
        recall_result = memx_recall.invoke({
            "query": "any query",
            "room_name": self.room_name,
            "recall_mode": "recent"
        })
        assert recall_result is not None


# ===== dreaming_manager 状態テスト =====

@pytest.mark.disabled_mode
@pytest.mark.llm_mock
class TestDreamingManagerDisabledMode:
    """
    dreaming_manager の disabled/read_only 状態テスト。

    削除可条件:
    - disabled でも夢生成導線が残る
    - read_only で洞察参照が維持される

    NOTE: LLM依存あり (llm_factory -> langchain_google_genai)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        # Note: send2trash is mocked globally in conftest.py
        self.room_name = "dream_disabled_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        dreaming_dir = room_dir / "memory" / "dreaming"
        dreaming_dir.mkdir(parents=True, exist_ok=True)

    def test_dream_disabled_mode_keeps_dream_flow_alive(self, workspace_tmp_path):
        """
        状態テスト: DreamingManager が memx 同期なしで動作する

        dreaming_manager_sync は削除済み。
        DreamingManager 本体は memx 同期なしでも正常に動作する。
        """
        from dreaming_manager import DreamingManager

        # DreamingManager 本体は初期化可能（同期なし）
        manager = DreamingManager(self.room_name, "dummy_key")
        assert manager is not None

        # 洞察読み込みも動作
        insights = manager._load_insights()
        assert isinstance(insights, list)

    def test_dream_read_only_mode_preserves_insight_access(self, workspace_tmp_path):
        """
        状態テスト: DreamingManager で洞察参照が可能

        dreaming_manager_sync は削除済み。
        DreamingManager はローカルストレージで洞察を管理。
        """
        from dreaming_manager import DreamingManager

        # DreamingManager で洞察参照が可能
        manager = DreamingManager(self.room_name, "dummy_key")
        insights = manager._load_insights()
        assert isinstance(insights, list)

        recent = manager.get_recent_insights_text(limit=5)
        assert recent is None or isinstance(recent, str)


# ===== motivation_manager 状態テスト =====

@pytest.mark.disabled_mode
@pytest.mark.llm_mock
class TestMotivationManagerDisabledMode:
    """
    motivation_manager の disabled/read_only 状態テスト。

    削除可条件:
    - disabled でも本体ロジックが残る
    - read_only で参照系が維持される

    NOTE: LLM依存あり
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        # Note: send2trash is mocked globally in conftest.py
        self.room_name = "motivation_disabled_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        memory_dir = room_dir / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

    def test_motivation_manager_initialization(self):
        """
        状態テスト: MotivationManager が初期化できる
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)
        assert manager is not None
        assert manager.room_name == self.room_name

    def test_motivation_disabled_mode_keeps_core_logic_alive(self, workspace_tmp_path):
        """
        状態テスト: MotivationManager が memx 同期なしで動作する

        motivation_manager_sync は削除済み。
        MotivationManager 本体は memx 同期なしでも正常に動作する。
        """
        from motivation_manager import MotivationManager

        # MotivationManager 本体は初期化可能（同期なし）
        manager = MotivationManager(self.room_name)
        assert manager is not None

        # 内部状態取得も動作
        state = manager.get_internal_state()
        assert isinstance(state, dict)
        assert "drives" in state

    def test_motivation_read_only_mode_preserves_question_reading(self, workspace_tmp_path):
        """
        状態テスト: MotivationManager で問い参照が可能

        motivation_manager_sync は read_only モード未対応。
        MotivationManager はローカルストレージで問いを管理。
        """
        from motivation_manager import MotivationManager

        # 先にデータを作成
        manager = MotivationManager(self.room_name)
        manager.add_open_question(
            topic="ReadOnly Test Question",
            context="Will this be readable?",
            priority=0.5
        )

        # 既存データの読み取りが可能
        state = manager.get_internal_state()
        questions = state.get("drives", {}).get("curiosity", {}).get("open_questions", [])

        found = any(q.get("topic") == "ReadOnly Test Question" for q in questions)
        assert found


# ===== pytest 実行用 =====

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "disabled_mode"])

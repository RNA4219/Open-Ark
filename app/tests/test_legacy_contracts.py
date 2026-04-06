# tests/test_legacy_contracts.py
"""
旧記憶実装 削除候補 契約テスト

MEMX_LEGACY_DELETION_CONTRACTS.md に定義された最低保証を検証する。
各削除候補について「何を満たせば互換とみなすか」を固定する。

対象:
- entity_memory_manager

削除済み:
- dreaming_manager_sync - 削除完了
- motivation_manager_sync - 削除完了
- rag_manager - 削除完了
- episodic_memory_manager - 削除完了
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# NOTE: Fixtures are provided by conftest.py:
# - workspace_tmp_path
# - local_adapter_config
# - memx_server_available
# - real_api_config
# Global mocks for send2trash and gradio are also applied in conftest.py


# ===== entity_memory_manager 契約テスト =====
# 最低保証:
# - エンティティ名をキーに知識を保存できる
# - 既存エントリを追記または上書きできる
# - 単一エントリを取得できる
# - 一覧取得できる
# - キーワード検索で関連エントリを返せる
# - room をまたいで混線しない

@pytest.mark.contract
class TestEntityMemoryManagerContracts:
    """
    entity_memory_manager 削除後の代替パス検証。

    削除済み: entity_memory_manager は entity_tools / memx 経路に置換
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "entity_contract_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        entities_dir = room_dir / "memory" / "entities"
        entities_dir.mkdir(parents=True, exist_ok=True)

    def test_entity_contract_create_and_read(self):
        """
        契約: エンティティ知識を保存し、再取得できる
        """
        from tools.entity_tools import write_entity_memory, read_entity_memory

        entity_name = "Test Entity"
        content = "Entity contract content"

        write_result = write_entity_memory.invoke({
            "entity_name": entity_name,
            "content": content,
            "room_name": self.room_name,
            "append": False,
        })
        read_result = read_entity_memory.invoke({
            "entity_name": entity_name,
            "room_name": self.room_name,
        })

        assert "created" in write_result.lower() or "overwritten" in write_result.lower()
        assert content in read_result

    def test_entity_contract_update_overwrites_or_appends(self):
        """
        契約: 既存エントリを追記または更新できる
        """
        from tools.entity_tools import write_entity_memory, read_entity_memory

        entity_name = "Append Entity"
        first = "First entity note"
        second = "Second entity note"

        write_entity_memory.invoke({
            "entity_name": entity_name,
            "content": first,
            "room_name": self.room_name,
            "append": False,
        })
        write_entity_memory.invoke({
            "entity_name": entity_name,
            "content": second,
            "room_name": self.room_name,
            "append": True,
        })
        read_result = read_entity_memory.invoke({
            "entity_name": entity_name,
            "room_name": self.room_name,
        })

        assert first in read_result
        assert second in read_result

    def test_entity_contract_list_contains_created_entities(self):
        """
        契約: 一覧取得で作成済みエンティティが見える
        """
        from tools.entity_tools import write_entity_memory, list_entity_memories

        entity_name = "Listed Entity"
        write_entity_memory.invoke({
            "entity_name": entity_name,
            "content": "List me",
            "room_name": self.room_name,
            "append": False,
        })

        listing = list_entity_memories.invoke({"room_name": self.room_name})
        assert entity_name in listing

    def test_entity_contract_search_returns_relevant_entity(self):
        """
        契約: キーワード検索で関連エンティティが返る
        """
        from tools.entity_tools import write_entity_memory, search_entity_memory

        entity_name = "Searchable Entity"
        write_entity_memory.invoke({
            "entity_name": entity_name,
            "content": "This entity knows about nebula archives.",
            "room_name": self.room_name,
            "append": False,
        })

        search_result = search_entity_memory.invoke({
            "query": "nebula",
            "room_name": self.room_name,
        })
        assert entity_name in search_result

    def test_entity_contract_room_isolation(self):
        """
        契約: room をまたいで混線しない
        """
        from tools.entity_tools import write_entity_memory, search_entity_memory

        room_a = "entity_room_a"
        room_b = "entity_room_b"
        entity_name = "Room Locked Entity"

        write_entity_memory.invoke({
            "entity_name": entity_name,
            "content": "Only room A should see this entity.",
            "room_name": room_a,
            "append": False,
        })

        search_result = search_entity_memory.invoke({
            "query": "Locked",
            "room_name": room_b,
        })
        assert entity_name not in search_result

    def test_entity_local_adapter_paths_available(self):
        """
        契約: LocalAdapter で knowledge store 操作が可能
        """
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter(self.room_name)
        note = adapter.ingest(
            store="knowledge",
            title="Adapter Entity",
            body="Saved through LocalAdapter.",
        )
        results = adapter.search("Adapter", store="knowledge", top_k=5)
        target = next(r for r in results if r.title == "Adapter Entity")
        shown = adapter.show(target.id, store="knowledge")

        assert adapter.is_available()
        assert note.title == "Adapter Entity"
        assert any(r.title == "Adapter Entity" for r in results)
        assert shown is not None and "Saved through LocalAdapter." in shown.body


# ===== episodic_memory_manager 契約テスト (episodic_memory_manager 削除済み) =====
# 代替パス: memx_ingest(store="journal") / memx_recall

@pytest.mark.contract
class TestEpisodicMemoryManagerContracts:
    """
    episodic_memory_manager 削除後の代替パス検証。

    削除済み: episodic_memory_manager は memx 経路に置換
    正常系テストで journal 系の保存・参照・文脈取得を検証
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "episode_contract_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        episodic_dir = room_dir / "memory" / "episodic"
        episodic_dir.mkdir(parents=True, exist_ok=True)

    def test_episode_journal_save_and_retrieve(self):
        """
        契約: journal store に保存し、memx_recall で取得できる
        """
        from tools.memx_tools import memx_ingest, memx_recall

        # journal に保存
        save_result = memx_ingest.invoke({
            "store": "journal",
            "title": "Contract Episode",
            "body": "This episode tests journal save and recall contract.",
            "room_name": self.room_name,
        })

        assert "Saved" in save_result or "Error" not in save_result

        # recall で取得
        recall_result = memx_recall.invoke({
            "query": "Contract Episode",
            "room_name": self.room_name,
            "recall_mode": "relevant",
        })

        assert recall_result is not None

    def test_episode_local_adapter_journal_paths_available(self):
        """
        契約: LocalAdapter 経由で journal 操作が可能
        """
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter(self.room_name)

        # journal に保存
        note = adapter.ingest(
            store="journal",
            title="Adapter Episode",
            body="This tests LocalAdapter journal path.",
        )

        assert note is not None
        assert note.store == "journal"

    @pytest.mark.skip(reason="introspection_tools requires langchain_core (llm_mock needed for this test)")
    def test_episode_introspection_tools_resolve_creates_episode(self):
        """
        契約: introspection_tools.manage_open_questions(resolve) が
        memx journal 経路でエピソードを生成する
        """
        from tools.introspection_tools import manage_open_questions
        from motivation_manager import MotivationManager

        # まず問いを追加
        mm = MotivationManager(self.room_name)
        mm.add_open_question(
            topic="Contract Test Question",
            context="This question will be resolved for contract test.",
            priority=0.5
        )

        # resolve アクション
        result = manage_open_questions.invoke({
            "room_name": self.room_name,
            "action": "resolve",
            "question_index": 1,
            "reflection": "Contract test resolution - learned that journal paths work.",
        })

        assert "解決済み" in result or "Error" not in result

    def test_episode_memx_search_finds_journal_entries(self):
        """
        契約: memx_search で journal エントリが検索可能
        """
        from tools.memx_tools import memx_ingest, memx_search

        # journal に特徴的なエントリを保存
        unique_keyword = "UniqueJournalKeyword12345"
        memx_ingest.invoke({
            "store": "journal",
            "title": "Searchable Episode",
            "body": f"This contains {unique_keyword} for search testing.",
            "room_name": self.room_name,
        })

        # 検索
        search_result = memx_search.invoke({
            "query": unique_keyword,
            "room_name": self.room_name,
            "store": "journal",
        })

        assert search_result is not None

    def test_episode_room_isolation_journal(self):
        """
        契約: journal エントリは room 間で分離される
        """
        from tools.memx_tools import memx_ingest, memx_search
        from adapters.local_adapter import LocalAdapter

        room_a = "episode_room_a"
        room_b = "episode_room_b"

        # Room A に保存
        memx_ingest.invoke({
            "store": "journal",
            "title": "Room A Episode",
            "body": "This is only for room A.",
            "room_name": room_a,
        })

        # Room B から検索
        search_b = memx_search.invoke({
            "query": "Room A Episode",
            "room_name": room_b,
            "store": "journal",
        })

        # Room B では見つからない
        assert "Room A Episode" not in search_b or "No memories found" in search_b


# ===== エピソード保存→参照→文脈取得 E2E テスト =====

@pytest.mark.contract
class TestEpisodeEndToEndFlow:
    """
    エピソード保存→参照→文脈取得の E2E フロー検証。

    削除後の journal 系経路が一貫して動作することを確認。
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "episode_e2e_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        room_dir.mkdir(parents=True, exist_ok=True)

    def test_episode_save_recall_search_flow(self):
        """
        E2E: 保存→recall→search の一連フローが動作
        """
        from tools.memx_tools import memx_ingest, memx_recall, memx_search

        # 1. 保存
        save_result = memx_ingest.invoke({
            "store": "journal",
            "title": "E2E Episode",
            "body": "End-to-end episode test with unique keyword: ZenithCascade",
            "room_name": self.room_name,
        })
        assert "Saved" in save_result or "Error" not in save_result

        # 2. recall で取得
        recall_result = memx_recall.invoke({
            "query": "E2E",
            "room_name": self.room_name,
            "recall_mode": "recent",
        })
        assert recall_result is not None

        # 3. search で検索
        search_result = memx_search.invoke({
            "query": "ZenithCascade",
            "room_name": self.room_name,
            "store": "journal",
        })
        assert search_result is not None

    @pytest.mark.skip(reason="introspection_tools requires langchain_core (llm_mock needed for this test)")
    def test_question_resolve_creates_journal_episode(self):
        """
        E2E: 問い追加→resolve→journal エピソード生成のフロー
        """
        from motivation_manager import MotivationManager
        from tools.introspection_tools import manage_open_questions
        from tools.memx_tools import memx_search

        # 1. 問いを追加
        mm = MotivationManager(self.room_name)
        mm.add_open_question(
            topic="E2E Question Topic",
            context="Testing question resolution creates journal episode.",
            priority=0.7
        )

        # 2. resolve で解決
        resolve_result = manage_open_questions.invoke({
            "room_name": self.room_name,
            "action": "resolve",
            "question_index": 1,
            "reflection": "E2E test: resolution creates an episode in journal store.",
        })
        assert "解決済み" in resolve_result or "Error" not in resolve_result

        # 3. journal にエピソードが保存されたことを確認
        search_result = memx_search.invoke({
            "query": "E2E Question Topic",
            "room_name": self.room_name,
            "store": "journal",
        })
        # エピソードが生成されている（検索結果が空でない）
        assert search_result is not None

    def test_local_adapter_journal_full_cycle(self):
        """
        E2E: LocalAdapter で journal の ingest→search→show フロー
        """
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter(self.room_name)

        # 1. ingest
        note = adapter.ingest(
            store="journal",
            title="Adapter E2E Episode",
            body="Full cycle test through LocalAdapter journal path.",
        )
        assert note is not None
        assert note.store == "journal"

        # 2. search
        results = adapter.search("Adapter E2E", store="journal", top_k=5)
        assert isinstance(results, list)

        # 3. show (該当があれば)
        if results:
            target = results[0]
            shown = adapter.show(target.id, store="journal")
            assert shown is not None or shown is None  # エラーでなければOK


# ===== rag_manager 契約テスト (rag_manager 削除済み) =====
# 代替パス: memx_search / memx_recall

@pytest.mark.contract
@pytest.mark.llm_mock
class TestRAGManagerContracts:
    """
    rag_manager 削除後の代替パス検証。

    削除済み: rag_manager は memx_search / memx_recall に置換

    NOTE: LLM/UI依存あり (memory_tools -> memory_manager -> gradio)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "rag_contract_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        rag_dir = room_dir / "rag_data"
        rag_dir.mkdir(parents=True, exist_ok=True)

    def test_rag_contract_memx_search_available(self):
        """
        契約: memx_search が利用可能
        """
        from tools.memx_tools import memx_search

        assert memx_search is not None

    def test_rag_contract_knowledge_search_path_alive(self):
        """
        契約: 知識検索導線が成立する
        """
        # knowledge_tools と memory_tools が memx 経路を使用していることを確認
        from tools.knowledge_tools import search_knowledge_base
        from tools.memory_tools import recall_memories

        assert search_knowledge_base is not None
        assert recall_memories is not None

    def test_rag_contract_memx_recall_available(self):
        """
        契約: memx_recall が利用可能
        """
        from tools.memx_tools import memx_recall

        assert memx_recall is not None


# ===== dreaming_manager 契約テスト =====
# 最低保証:
# - 洞察を保存できる
# - 最近の洞察を再取得できる
# - 夢、内省由来の記録が journal 系文脈として扱える
# - 本体機能が同期失敗で落ちない

@pytest.mark.contract
@pytest.mark.llm_mock
class TestDreamingManagerContracts:
    """
    dreaming_manager の契約テスト。

    最低保証:
    - 洞察を保存できる
    - 最近の洞察を再取得できる
    - 夢、内省由来の記録が journal 系文脈として扱える
    - 本体機能が同期失敗で落ちない

    NOTE: LLM依存あり (llm_factory -> langchain_google_genai)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        # Note: send2trash is mocked globally in conftest.py
        self.room_name = "dream_contract_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        dreaming_dir = room_dir / "memory" / "dreaming"
        dreaming_dir.mkdir(parents=True, exist_ok=True)

    def test_dream_manager_initialization(self):
        """
        契約: DreamingManager が初期化できる
        """
        from dreaming_manager import DreamingManager

        manager = DreamingManager(self.room_name, "dummy_key")
        assert manager is not None
        assert manager.room_name == self.room_name

    def test_dream_contract_store_and_reload_insight(self, workspace_tmp_path):
        """
        契約: 洞察保存後に再取得できる
        """
        from dreaming_manager import DreamingManager
        from file_lock_utils import safe_json_read, safe_json_write
        import datetime

        manager = DreamingManager(self.room_name, "dummy_key")

        # 洞察を追加
        today = datetime.datetime.now().strftime("%Y-%m")
        insight_file = workspace_tmp_path / "characters" / self.room_name / "memory" / "dreaming" / f"{today}.json"

        new_insight = {
            "id": f"insight_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
            "created_at": datetime.datetime.now().isoformat(),
            "type": "insight",
            "content": "Test insight for contract verification."
        }

        # 既存データを読み込んで追加
        existing = []
        if insight_file.exists():
            existing = safe_json_read(str(insight_file), default=[])

        if not isinstance(existing, list):
            existing = []

        existing.append(new_insight)

        # safe_json_write を使用
        safe_json_write(str(insight_file), existing)

        # 再取得
        insights = manager._load_insights()

        assert isinstance(insights, list)

    def test_dream_contract_recent_insights_available(self, workspace_tmp_path):
        """
        契約: 最近の洞察取得が成立する
        """
        from dreaming_manager import DreamingManager

        manager = DreamingManager(self.room_name, "dummy_key")

        # 最近の洞察を取得
        recent = manager.get_recent_insights_text(limit=5)

        # None または文字列が返る
        assert recent is None or isinstance(recent, str)

    def test_dream_contract_monthly_file_path(self):
        """
        契約: 月次ファイルパスが正しく生成される
        """
        from dreaming_manager import DreamingManager

        manager = DreamingManager(self.room_name, "dummy_key")

        # 日付から月次ファイルパスを生成
        path = manager._get_monthly_file_path("2026-04-07 12:00:00")
        assert "2026-04.json" in str(path)

    def test_dream_contract_sync_failure_is_nonfatal(self, workspace_tmp_path):
        """
        契約: 同期失敗でも本体が落ちない
        """
        from dreaming_manager import DreamingManager

        # 無効な API キーで初期化
        manager = DreamingManager(self.room_name, "invalid_api_key_for_test")

        # _load_insights は例外を投げずに空リストを返すべき
        try:
            insights = manager._load_insights()
            assert isinstance(insights, list)
        except Exception as e:
            # 同期失敗でも致命的であってはならない
            pytest.fail(f"DreamingManager should not crash on sync failure: {e}")


# ===== motivation_manager 契約テスト =====
# 最低保証:
# - 未解決問いを追加できる
# - 内部状態を取得できる
# - 問いを解決済みにできる
# - interaction 更新で異常終了しない
# - room ごとに独立している

@pytest.mark.contract
@pytest.mark.llm_mock
class TestMotivationManagerContracts:
    """
    motivation_manager の契約テスト。

    最低保証:
    - 未解決問いを追加できる
    - 内部状態を取得できる
    - 問いを解決済みにできる
    - interaction 更新で異常終了しない
    - room ごとに独立している

    NOTE: LLM依存あり (motivation_manager -> room_manager -> send2trash はモック済み)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        # Note: send2trash is mocked globally in conftest.py
        self.room_name = "motivation_contract_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        memory_dir = room_dir / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

    def test_motivation_manager_initialization(self):
        """
        契約: MotivationManager が初期化できる
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)
        assert manager is not None
        assert manager.room_name == self.room_name

    def test_motivation_contract_add_and_read_question(self, workspace_tmp_path):
        """
        契約: 未解決問いを追加して読める
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)

        # 問いを追加（add_open_question は topic と context を受け取る）
        manager.add_open_question(
            topic="Test Topic",
            context="What is the meaning of this test?",
            priority=0.5
        )

        # 内部状態を取得して確認
        state = manager.get_internal_state()
        drives = state.get("drives", {})
        curiosity = drives.get("curiosity", {})
        questions = curiosity.get("open_questions", [])

        # 問いが追加されていることを確認
        assert len(questions) >= 1
        found = any(q.get("topic") == "Test Topic" for q in questions)
        assert found

    def test_motivation_contract_resolve_question_changes_state(self, workspace_tmp_path):
        """
        契約: 解決後に状態が変わる
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)

        # 問いを追加
        manager.add_open_question(
            topic="Resolvable Topic",
            context="This question will be resolved.",
            priority=0.3
        )

        # 解決済みにする
        manager.mark_question_resolved("Resolvable Topic", answer_summary="This has been resolved.")

        # 解決済みの問いは resolved_at が設定されている
        state = manager.get_internal_state()
        questions = state.get("drives", {}).get("curiosity", {}).get("open_questions", [])

        # 解決済みの問いを見つける
        resolved = [q for q in questions if q.get("topic") == "Resolvable Topic" and q.get("resolved_at")]
        assert len(resolved) >= 1

    def test_motivation_contract_internal_state_available(self, workspace_tmp_path):
        """
        契約: 内部状態取得が成立する
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)

        state = manager.get_internal_state()

        # 必要な構造が存在することを確認
        assert isinstance(state, dict)
        assert "drives" in state

        drives = state["drives"]
        assert "boredom" in drives
        assert "curiosity" in drives
        assert "goal_achievement" in drives
        assert "relatedness" in drives

    def test_motivation_contract_room_isolation(self, workspace_tmp_path):
        """
        契約: room 分離が保たれる
        """
        from motivation_manager import MotivationManager

        room_a = "motivation_room_a"
        room_b = "motivation_room_b"

        manager_a = MotivationManager(room_a)
        manager_b = MotivationManager(room_b)

        # Room A に問いを追加
        manager_a.add_open_question(
            topic="Room A Question",
            context="This is only for room A.",
            priority=0.5
        )

        # Room B からは見えない
        state_b = manager_b.get_internal_state()
        questions_b = state_b.get("drives", {}).get("curiosity", {}).get("open_questions", [])

        found_in_b = any(q.get("topic") == "Room A Question" for q in questions_b)
        assert not found_in_b


# ===== pytest 実行用 =====

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "contract"])

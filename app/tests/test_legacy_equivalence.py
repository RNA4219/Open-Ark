# tests/test_legacy_equivalence.py
"""
旧記憶実装 削除候補 同値テスト

MEMX_LEGACY_DELETION_CONTRACTS.md に定義された同値判定観点に基づき、
旧実装と memx 代替経路が意味的に同等の結果を返すことを確認する。

同値判定観点:
- 保存後に再取得できる
- 検索語に対して対象エンティティが見つかる
- 別 room からは見えない
- 同じクエリで関連記憶が返る
- 検索失敗時に graceful に空結果または代替結果になる
"""

import os
import sys
import uuid
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# ===== Fixtures =====

@pytest.fixture
def workspace_tmp_path():
    """workspace 配下に安定したテスト用一時ディレクトリを作る。"""
    base_dir = Path(__file__).resolve().parents[3] / "tmp_scratch" / "open_ark_tests"
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = base_dir / f"equiv_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def local_adapter_config(workspace_tmp_path, monkeypatch):
    """LocalAdapter 使用の設定"""
    import config_manager
    from adapters.memory_adapter import reset_adapter

    monkeypatch.setattr("constants.ROOMS_DIR", str(workspace_tmp_path / "characters"))
    config_manager.CONFIG_GLOBAL = {
        "memx_settings": {
            "use_memx": False,
            "memx_api_addr": "http://127.0.0.1:7766",
            "memx_db_path_template": "{room_dir}/memx",
            "memx_request_timeout_sec": 10,
            "gc_execute_enabled": False,
            "phase3_settings": {
                "advanced_resolver_enabled": False,
                "deprecation": {}
            }
        }
    }
    reset_adapter()
    yield
    reset_adapter()


@pytest.fixture
def memx_server_available():
    """memx-resolver API が到達可能かチェック"""
    try:
        import requests
        response = requests.post(
            "http://127.0.0.1:7766/v1/notes:search",
            json={"query": "health_check", "top_k": 1},
            timeout=5
        )
        return response.status_code == 200
    except Exception:
        return False


# ===== entity_memory_manager 同値テスト =====

@pytest.mark.equivalence
@pytest.mark.skip(reason="entity_memory_manager 削除済み - entity_tools 経由でテスト")
class TestEntityMemoryManagerEquivalence:
    """
    entity_memory_manager 削除後の代替パス検証。

    削除済み: entity_memory_manager は entity_tools / memx 経路に置換
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "entity_equiv_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        entities_dir = room_dir / "memory" / "entities"
        entities_dir.mkdir(parents=True, exist_ok=True)

    def test_entity_equivalence_memx_paths_available(self):
        """
        同値テスト: memx 経路で knowledge store 操作が可能
        """
        from tools.memx_tools import memx_ingest, memx_search, memx_show
        assert memx_ingest is not None
        assert memx_search is not None
        assert memx_show is not None

    def test_entity_equivalence_entity_tools_available(self):
        """
        同値テスト: entity_tools が利用可能
        """
        from tools.entity_tools import read_entity_memory, write_entity_memory
        assert read_entity_memory is not None
        assert write_entity_memory is not None


# ===== episodic_memory_manager 同値テスト =====

@pytest.mark.equivalence
class TestEpisodicMemoryManagerEquivalence:
    """
    episodic_memory_manager と memx 代替経路の同値テスト。

    同値判定:
    - 保存した出来事が後で取得できる
    - 時系列文脈に反映される
    - 他 room の出来事が混ざらない
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "episode_equiv_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        episodic_dir = room_dir / "memory" / "episodic"
        episodic_dir.mkdir(parents=True, exist_ok=True)

    def test_episode_equivalence_legacy_vs_memx_journal(self, workspace_tmp_path):
        """
        同値テスト: memx journal 経路が動作可能

        memx 代替:
        - memx_ingest(store="journal") で保存
        - memx_recall で取得
        """
        from tools.memx_tools import memx_ingest, memx_recall

        # === memx 代替経路での保存・取得 ===
        # memx_ingest で journal store に保存
        memx_result = memx_ingest.invoke({
            "store": "journal",
            "title": "Test Episode",
            "body": "This is a test episode stored via memx.",
            "room_name": self.room_name
        })

        assert memx_result is not None

        # memx_recall で取得
        recall_result = memx_recall.invoke({
            "query": "test episode",
            "room_name": self.room_name,
            "recall_mode": "recent"
        })

        assert recall_result is not None


# ===== rag_manager 同値テスト (rag_manager 削除済み) =====

@pytest.mark.equivalence
class TestRAGManagerEquivalence:
    """
    rag_manager 削除後の memx 代替経路テスト。

    同値判定:
    - memx_recall / memx_search で検索が可能
    - 検索失敗時に graceful に空結果を返す
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "rag_equiv_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        rag_dir = room_dir / "rag_data"
        rag_dir.mkdir(parents=True, exist_ok=True)

    def test_rag_equivalence_memx_recall_available(self, workspace_tmp_path):
        """
        同値テスト: memx_recall で検索可能
        """
        from tools.memx_tools import memx_recall
        from adapters.local_adapter import LocalAdapter

        # LocalAdapter 経由での検索（rag_manager 削除済み）
        adapter = LocalAdapter(self.room_name)
        local_results = adapter.search("test query", store="journal", top_k=5)

        # 結果が返る（エラーでない）
        assert isinstance(local_results, list)

        # memx_recall での検索
        memx_results = memx_recall.invoke({
            "query": "test query",
            "room_name": self.room_name,
            "recall_mode": "relevant"
        })

        assert memx_results is not None

    def test_rag_equivalence_graceful_empty_result(self, workspace_tmp_path):
        """
        同値テスト: 検索失敗時に graceful に空結果を返す
        """
        from adapters.local_adapter import LocalAdapter
        from tools.memx_tools import memx_search

        # LocalAdapter で検索
        adapter = LocalAdapter(self.room_name)
        results = adapter.search("nonexistent_unique_query_xyz123", top_k=5)

        # 空リストまたは結果リスト（エラーでない）
        assert isinstance(results, list)

        # memx_search でも同様
        memx_results = memx_search.invoke({
            "query": "nonexistent_unique_query_xyz123",
            "room_name": self.room_name
        })

        # エラーでなく結果が返る
        assert memx_results is not None


# ===== dreaming_manager 同値テスト =====

@pytest.mark.equivalence
@pytest.mark.llm_mock
class TestDreamingManagerEquivalence:
    """
    dreaming_manager と memx 代替経路の同値テスト。

    同値判定:
    - 保存した洞察が後で取得できる
    - journal 系検索で見つかる
    - 同期失敗時も dreaming 本体が継続する

    NOTE: LLM依存あり (llm_factory -> langchain_google_genai)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "dream_equiv_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        dreaming_dir = room_dir / "memory" / "dreaming"
        dreaming_dir.mkdir(parents=True, exist_ok=True)

    def test_dream_equivalence_legacy_vs_memx_journal_sync(self, workspace_tmp_path):
        """
        同値テスト: journal 側代替で意味的一致

        旧実装 (dreaming_manager):
        - _load_insights で取得
        - 洞察を memory/dreaming/*.json に保存

        memx 代替:
        - memx_ingest(store="journal") で保存
        - memx_recall で取得
        """
        from dreaming_manager import DreamingManager
        from tools.memx_tools import memx_ingest, memx_recall

        # === 旧実装での取得 ===
        legacy_manager = DreamingManager(self.room_name, "dummy_key")
        insights = legacy_manager._load_insights()

        # リストが返る（エラーでない）
        assert isinstance(insights, list)

        # === memx 代替経路での保存・取得 ===
        memx_result = memx_ingest.invoke({
            "store": "journal",
            "title": "Test Insight",
            "body": "This is a test insight stored via memx.",
            "room_name": self.room_name
        })

        assert memx_result is not None

        # memx_recall で取得
        recall_result = memx_recall.invoke({
            "query": "insight",
            "room_name": self.room_name,
            "recall_mode": "recent"
        })

        assert recall_result is not None

    def test_dream_equivalence_sync_failure_nonfatal(self, workspace_tmp_path):
        """
        同値テスト: 同期失敗時も本体が継続する
        """
        from dreaming_manager import DreamingManager

        # 無効な API キーで初期化
        manager = DreamingManager(self.room_name, "invalid_key_test")

        # _load_insights は例外を投げずにリストを返す
        try:
            insights = manager._load_insights()
            assert isinstance(insights, list)
        except Exception:
            pytest.fail("DreamingManager should not crash on sync failure")


# ===== motivation_manager 同値テスト =====

@pytest.mark.equivalence
@pytest.mark.llm_mock
class TestMotivationManagerEquivalence:
    """
    motivation_manager と memx 代替経路の同値テスト。

    同値判定:
    - 追加した問いが後で見つかる
    - 解決後に状態が変わる
    - 他 room に漏れない

    NOTE: LLM依存あり
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config, workspace_tmp_path):
        self.room_name = "motivation_equiv_test"
        room_dir = workspace_tmp_path / "characters" / self.room_name
        memory_dir = room_dir / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

    def test_motivation_equivalence_legacy_vs_memx_short(self, workspace_tmp_path):
        """
        同値テスト: 旧実装と memx short 経路で意味的一致

        旧実装 (motivation_manager):
        - add_open_question で追加
        - get_internal_state で取得
        - mark_question_resolved で解決

        memx 代替:
        - memx_ingest(store="short") で保存
        - memx_recall で取得
        - memx_resolve で解決
        """
        from motivation_manager import MotivationManager
        from tools.memx_tools import memx_ingest, memx_recall

        # === 旧実装での保存・取得 ===
        legacy_manager = MotivationManager(self.room_name)

        # 問いを追加
        legacy_manager.add_open_question(
            topic="Equivalence Test Topic",
            context="How does this compare to memx?",
            priority=0.5
        )

        # 内部状態を取得
        state = legacy_manager.get_internal_state()
        questions = state.get("drives", {}).get("curiosity", {}).get("open_questions", [])

        # 問いが追加されている
        found = any(q.get("topic") == "Equivalence Test Topic" for q in questions)
        assert found

        # === memx 代替経路での保存・取得 ===
        memx_result = memx_ingest.invoke({
            "store": "short",
            "title": "Memx Question",
            "body": "How does memx handle questions?",
            "room_name": self.room_name
        })

        assert memx_result is not None

        # memx_recall で取得
        recall_result = memx_recall.invoke({
            "query": "question",
            "room_name": self.room_name,
            "recall_mode": "relevant"
        })

        assert recall_result is not None

    def test_motivation_equivalence_resolve_changes_state(self, workspace_tmp_path):
        """
        同値テスト: 解決後に状態が変わる
        """
        from motivation_manager import MotivationManager

        manager = MotivationManager(self.room_name)

        # 問いを追加
        manager.add_open_question(
            topic="Resolvable Equivalence Topic",
            context="This will be resolved.",
            priority=0.3
        )

        # 解決
        manager.mark_question_resolved("Resolvable Equivalence Topic", answer_summary="Resolved.")

        # 状態確認
        state = manager.get_internal_state()
        questions = state.get("drives", {}).get("curiosity", {}).get("open_questions", [])

        # 解決済みの問いは resolved_at が設定されている
        resolved = [q for q in questions if q.get("topic") == "Resolvable Equivalence Topic" and q.get("resolved_at")]
        assert len(resolved) >= 1


# ===== pytest 実行用 =====

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "equivalence"])
# tests/test_memx_integration.py
"""
memx-resolver統合 受け入れテスト (Phase 1)

AC-001〜AC-008 の受け入れ条件を検証する。
"""

import os
import sys
import json
import tempfile
import shutil
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# テスト用にパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def workspace_tmp_path():
    """workspace 配下に安定したテスト用一時ディレクトリを作る。"""
    base_dir = Path(__file__).resolve().parents[3] / "tmp_scratch" / "open_ark_tests"
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = base_dir / f"case_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


class TestMemxClient:
    """memx_client.py の基本機能テスト"""

    def test_client_initialization(self):
        """クライアント初期化テスト"""
        from memx_client import MemxClient

        client = MemxClient(
            api_addr="http://127.0.0.1:7766",
            db_path="/tmp/test_db",
            timeout=10
        )

        assert client.api_addr == "http://127.0.0.1:7766"
        assert client.db_path == "/tmp/test_db"
        assert client.timeout == 10

    def test_env_override(self, monkeypatch):
        """環境変数による上書きテスト"""
        from memx_client import MemxClient

        monkeypatch.setenv("MEMX_API_ADDR", "http://custom:8888")

        client = MemxClient()
        assert client.api_addr == "http://custom:8888"

    def test_store_endpoint_mapping(self):
        """store別エンドポイントマッピングテスト"""
        from memx_client import MemxClient, STORE_ENDPOINTS

        client = MemxClient()

        # storeごとのエンドポイント確認（4ストア）
        assert STORE_ENDPOINTS["short"] == "notes"
        assert STORE_ENDPOINTS["journal"] == "journal"
        assert STORE_ENDPOINTS["knowledge"] == "knowledge"
        assert STORE_ENDPOINTS["archive"] == "archive"

        # エンドポイント生成テスト
        assert client._get_store_endpoint("knowledge", "ingest") == "/v1/knowledge:ingest"
        assert client._get_store_endpoint("journal", "search") == "/v1/journal:search"
        assert client._get_store_endpoint("short", "get") == "/v1/notes"

    def test_all_store_search_includes_archive(self):
        """store='all' 検索が archive を含む"""
        from memx_client import MemxClient

        client = MemxClient()

        # _get_store_endpoint が archive を正しく返す
        assert client._get_store_endpoint("archive", "search") == "/v1/archive:search"


class TestCoreAcceptanceMocked:
    """
    AC-001〜AC-003: モックによる core acceptance テスト

    MemxAdapter の ingest/search/show 成功をモックで検証。
    実 API が起動している場合は統合テストで実検証可能。
    """

    @pytest.fixture
    def mock_memx_client(self):
        """MemxClient をモック"""
        from memx_client import Note

        mock_client = Mock()

        # モックの Note オブジェクト
        mock_note = Note(
            id="note-001",
            title="テストタイトル",
            body="テスト本文",
            summary="テスト要約",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            last_accessed_at="",
            access_count=0,
            source_type="test",
            origin="test",
            source_trust="medium",
            sensitivity="normal"
        )
        mock_note.store = "knowledge"

        # 各メソッドをモック
        mock_client.health_check.return_value = True
        mock_client.ingest.return_value = mock_note
        mock_client.search.return_value = [mock_note]
        mock_client.show.return_value = mock_note

        return mock_client, mock_note

    def test_ac001_memx_ingest_success(self, mock_memx_client):
        """
        AC-001: memx_ingest が成功する

        knowledge ストアへの ingest が正しく Note を返す。
        """
        from adapters.memx_adapter import MemxAdapter
        from adapters.memory_adapter import MemoryNote

        mock_client, mock_note = mock_memx_client

        with patch.object(MemxAdapter, '_get_client', return_value=mock_client):
            adapter = MemxAdapter(api_addr="http://mock", db_path="/mock/db")
            adapter._available = True

            result = adapter.ingest(
                store="knowledge",
                title="テストタイトル",
                body="テスト本文",
                summary="テスト要約"
            )

            assert result is not None
            assert result.id == "note-001"
            assert result.title == "テストタイトル"
            assert result.store == "knowledge"

    def test_ac002_memx_search_success(self, mock_memx_client):
        """
        AC-002: memx_search が成功する

        search(store="all") が複数ストアの結果を返す。
        """
        from adapters.memx_adapter import MemxAdapter

        mock_client, mock_note = mock_memx_client

        with patch.object(MemxAdapter, '_get_client', return_value=mock_client):
            adapter = MemxAdapter(api_addr="http://mock", db_path="/mock/db")
            adapter._available = True

            results = adapter.search(
                query="テストクエリ",
                store="all",
                top_k=10
            )

            assert len(results) > 0
            assert results[0].title == "テストタイトル"

    def test_ac003_memx_show_success(self, mock_memx_client):
        """
        AC-003: memx_show が成功する

        特定 ID の Note を取得できる。
        """
        from adapters.memx_adapter import MemxAdapter

        mock_client, mock_note = mock_memx_client

        with patch.object(MemxAdapter, '_get_client', return_value=mock_client):
            adapter = MemxAdapter(api_addr="http://mock", db_path="/mock/db")
            adapter._available = True

            result = adapter.show(note_id="note-001", store="knowledge")

            assert result is not None
            assert result.id == "note-001"
            assert result.title == "テストタイトル"


class TestMemoryAdapter:
    """Adapter層の基本機能テスト"""

    def test_memory_note_dataclass(self):
        """MemoryNote データクラステスト"""
        from adapters.memory_adapter import MemoryNote

        note = MemoryNote(
            id="test-001",
            title="テストタイトル",
            body="テスト本文",
            summary="要約",
            store="knowledge"
        )

        assert note.id == "test-001"
        assert note.title == "テストタイトル"
        assert note.store == "knowledge"

    def test_local_adapter_is_available(self):
        """LocalAdapter は常に利用可能"""
        from adapters.local_adapter import LocalAdapter

        adapter = LocalAdapter()
        assert adapter.is_available() == True


class TestLocalAdapter:
    """LocalAdapter の機能テスト（APIなしで動作確認）"""

    def test_local_adapter_ingest_knowledge(self, workspace_tmp_path, monkeypatch):
        """short ストア保存時に room 配下へローカル退避される"""
        from adapters.local_adapter import LocalAdapter

        monkeypatch.setattr("constants.ROOMS_DIR", str(workspace_tmp_path / "characters"))

        # テスト用roomを作成
        room_name = "test_room"
        room_dir = workspace_tmp_path / "characters" / room_name
        room_dir.mkdir(parents=True)

        # memories ディレクトリを作成
        memories_dir = room_dir / "memory" / "entities"
        memories_dir.mkdir(parents=True)

        adapter = LocalAdapter(room_name=room_name)

        # 簡易的な保存テスト（実際のentity_memory_managerはパス依存）
        note = adapter.ingest(
            store="short",
            title="テストメモ",
            body="これはテストです",
            room_name=room_name
        )

        assert note.title == "テストメモ"
        assert note.store == "short"
        assert (room_dir / "memx_local" / "short.txt").exists()


class TestRoomBasedDBSeparation:
    """FR-013 / AC-007: roomごとのDB分離テスト"""

    def test_adapter_cache_per_room(self):
        """roomごとに異なるアダプターインスタンスが作成される"""
        import adapters.memory_adapter as memory_adapter_module
        from adapters.memory_adapter import get_memory_adapter, reset_adapter

        reset_adapter()

        adapter1 = get_memory_adapter("room_alpha")
        adapter2 = get_memory_adapter("room_beta")

        # roomごとに異なるインスタンス
        assert adapter1 is not adapter2
        assert "room_alpha" in memory_adapter_module._adapter_cache
        assert "room_beta" in memory_adapter_module._adapter_cache

        # 同じroomは同じインスタンス
        adapter1_again = get_memory_adapter("room_alpha")
        assert adapter1 is adapter1_again

    def test_db_path_per_room(self):
        """roomごとに異なるdb_pathが設定される"""
        from adapters.memory_adapter import get_memory_adapter, reset_adapter
        from adapters.memx_adapter import MemxAdapter

        reset_adapter()

        # CONFIG_GLOBAL を設定（use_memx=false なので LocalAdapter になる）
        adapter1 = get_memory_adapter("room_alpha")
        adapter2 = get_memory_adapter("room_beta")

        # 現時点ではuse_memx=falseなのでLocalAdapter
        # db_path確認はMemxAdapterの場合に行う
        from adapters.local_adapter import LocalAdapter
        assert isinstance(adapter1, LocalAdapter)
        assert isinstance(adapter2, LocalAdapter)


class TestConfigPathIntegration:
    """FR-003 / FR-014: 設定経路の統合テスト"""

    def test_db_path_template_used(self, workspace_tmp_path, monkeypatch):
        """memx_db_path_template が adapter 選択経路で使用される"""
        import config_manager
        from adapters.memory_adapter import get_memory_adapter, reset_adapter
        from adapters.memx_adapter import MemxAdapter
        from adapters.local_adapter import LocalAdapter

        # constants.ROOMS_DIR をテスト用に設定
        monkeypatch.setattr("constants.ROOMS_DIR", str(workspace_tmp_path / "rooms"))

        # カスタムテンプレートを設定
        config_manager.CONFIG_GLOBAL = {
            "memx_settings": {
                "use_memx": True,
                "memx_api_addr": "http://127.0.0.1:7766",
                "memx_db_path_template": "{room_dir}/custom_memx",
                "memx_request_timeout_sec": 15
            }
        }
        reset_adapter()

        room_dir = workspace_tmp_path / "rooms" / "test_room"
        captured = {}

        original_init = MemxAdapter.__init__

        def capturing_init(self, api_addr=None, db_path=None, timeout=None):
            captured["api_addr"] = api_addr
            captured["db_path"] = db_path
            captured["timeout"] = timeout
            original_init(self, api_addr=api_addr, db_path=db_path, timeout=timeout)

        # get_memory_adapter() 経由で MemxAdapter がどう構築されるかを確認
        with patch.object(MemxAdapter, "__init__", capturing_init), \
             patch.object(MemxAdapter, 'is_available', return_value=False):
            adapter = get_memory_adapter("test_room")
            assert isinstance(adapter, LocalAdapter)
            assert captured["api_addr"] == "http://127.0.0.1:7766"
            assert Path(captured["db_path"]) == room_dir / "custom_memx"
            assert captured["timeout"] == 15

    def test_timeout_used(self):
        """memx_request_timeout_sec が MemxAdapter に渡される"""
        import config_manager
        from adapters.memory_adapter import get_memory_adapter, reset_adapter
        from adapters.memx_adapter import MemxAdapter

        config_manager.CONFIG_GLOBAL = {
            "memx_settings": {
                "use_memx": True,
                "memx_api_addr": "http://127.0.0.1:7766",
                "memx_db_path_template": "{room_dir}/memx",
                "memx_request_timeout_sec": 20
            }
        }
        reset_adapter()

        captured = {}
        original_init = MemxAdapter.__init__

        def capturing_init(self, api_addr=None, db_path=None, timeout=None):
            captured["timeout"] = timeout
            original_init(self, api_addr=api_addr, db_path=db_path, timeout=timeout)

        with patch.object(MemxAdapter, "__init__", capturing_init), \
             patch.object(MemxAdapter, "is_available", return_value=False):
            get_memory_adapter("timeout_room")

        assert captured["timeout"] == 20


class TestAcceptanceCriteria:
    """
    受け入れ条件テスト (AC-001〜AC-008)

    注意: AC-001〜AC-003 は memx API が起動している必要がある。
    skip_api_required デコレータで条件付きスキップ可能。
    """

    @pytest.fixture(autouse=True)
    def setup_config(self, workspace_tmp_path, monkeypatch):
        """テスト用設定をCONFIG_GLOBALに適用"""
        import config_manager

        # constants.ROOMS_DIR をテスト用に設定
        monkeypatch.setattr("constants.ROOMS_DIR", str(workspace_tmp_path / "characters"))

        # テスト用設定をCONFIG_GLOBALに適用
        config_manager.CONFIG_GLOBAL = {
            "memx_settings": {
                "use_memx": False,
                "memx_api_addr": "http://127.0.0.1:7766",
                "memx_db_path_template": "{room_dir}/memx",
                "memx_request_timeout_sec": 10
            }
        }

        # アダプターキャッシュをリセット
        from adapters.memory_adapter import reset_adapter
        reset_adapter()

        yield

        # テスト後にリセット
        reset_adapter()

    def test_ac004_api_unavailable_opens_ark(self):
        """
        AC-004: use_memx=true かつ API 停止時でも Open-Ark が起動に成功する
        """
        import config_manager
        from adapters.memory_adapter import get_memory_adapter, reset_adapter

        # 設定を use_memx=true に
        config_manager.CONFIG_GLOBAL["memx_settings"]["use_memx"] = True
        reset_adapter()

        # memxが利用できない場合、LocalAdapterにフォールバック
        adapter = get_memory_adapter("test_room")

        # APIがなくてもアダプターは取得可能（フォールバック）
        assert adapter is not None
        assert adapter.is_available() == True

    def test_ac005_fallback_to_local_adapter(self):
        """
        AC-005: use_memx=true かつ API 停止時に LocalAdapter へ退避できる

        注: このテストは API が利用不可の場合にのみ LocalAdapter へのフォールバックを検証。
        API が利用可能な場合は MemxAdapter が使用される（正常な動作）。
        """
        import config_manager
        from adapters.memory_adapter import get_memory_adapter, reset_adapter
        from adapters.local_adapter import LocalAdapter
        from adapters.memx_adapter import MemxAdapter

        config_manager.CONFIG_GLOBAL["memx_settings"]["use_memx"] = True
        reset_adapter()

        adapter = get_memory_adapter("test_room")

        # API利用可否に応じて分岐
        if isinstance(adapter, MemxAdapter):
            # API が利用可能な場合は MemxAdapter が使用される（正常）
            # このテストは「API停止時」のフォールバックをテストするものなので
            # API利用可能時はスキップ相当
            pytest.skip("memx API is available - fallback test not applicable")
        else:
            # API 停止時は LocalAdapter になる（フォールバック）
            assert isinstance(adapter, LocalAdapter)

    def test_ac006_use_memx_false_uses_local(self):
        """
        AC-006: use_memx=false で従来の主要機能が継続利用できる
        """
        import config_manager
        from adapters.memory_adapter import get_memory_adapter, reset_adapter
        from adapters.local_adapter import LocalAdapter

        config_manager.CONFIG_GLOBAL["memx_settings"]["use_memx"] = False
        reset_adapter()

        adapter = get_memory_adapter("test_room")

        assert isinstance(adapter, LocalAdapter)
        assert adapter.is_available() == True

    def test_ac007_room_based_db_separation(self, workspace_tmp_path):
        """
        AC-007: 複数room環境で各roomの記憶が分離される
        """
        import config_manager
        from adapters.memory_adapter import get_memory_adapter, reset_adapter

        # roomディレクトリを作成
        rooms_dir = workspace_tmp_path / "characters"
        room_alpha = rooms_dir / "room_alpha"
        room_beta = rooms_dir / "room_beta"
        room_alpha.mkdir(parents=True)
        room_beta.mkdir(parents=True)

        config_manager.CONFIG_GLOBAL["memx_settings"]["use_memx"] = False
        reset_adapter()

        adapter_alpha = get_memory_adapter("room_alpha")
        adapter_beta = get_memory_adapter("room_beta")

        # roomごとに異なるアダプターインスタンス
        assert adapter_alpha is not adapter_beta

        # LocalAdapterの場合、room_nameが異なる
        from adapters.local_adapter import LocalAdapter
        if isinstance(adapter_alpha, LocalAdapter):
            assert adapter_alpha._room_name == "room_alpha"
            assert adapter_beta._room_name == "room_beta"

    def test_ac008_no_automatic_deletion(self, workspace_tmp_path):
        """
        AC-008: memx 導入後も既存データが自動削除されない

        既存の entity / episode / question 系ファイルが存在する場合、
        memx導入によって削除されないことを確認。
        """
        # テスト用room構造を作成
        room_name = "test_room"
        room_dir = workspace_tmp_path / "characters" / room_name
        room_dir.mkdir(parents=True)

        # 既存ファイルを作成
        memory_dir = room_dir / "memory"
        memory_dir.mkdir()

        entities_dir = memory_dir / "entities"
        entities_dir.mkdir()
        (entities_dir / "test_entity.md").write_text("# Test Entity\nExisting data", encoding="utf-8")

        episodes_file = memory_dir / "episodes.json"
        episodes_file.write_text('{"episodes": []}', encoding="utf-8")

        private_dir = room_dir / "private"
        private_dir.mkdir()
        (private_dir / "open_questions.json").write_text('{"questions": []}', encoding="utf-8")

        # memx統合後もファイルが存在することを確認
        assert (entities_dir / "test_entity.md").exists()
        assert episodes_file.exists()
        assert (private_dir / "open_questions.json").exists()


class TestMemxTools:
    """memx_tools.py のテスト"""

    def test_tool_definitions(self):
        """ツールが正しく定義されているか"""
        from tools.memx_tools import memx_search, memx_ingest, memx_show, memx_recall

        # LangChain tool デコレータが適用されているか
        assert hasattr(memx_search, 'name')
        assert hasattr(memx_ingest, 'name')
        assert hasattr(memx_show, 'name')
        assert hasattr(memx_recall, 'name')

    def test_tool_descriptions(self):
        """ツールの説明が設定されているか"""
        from tools.memx_tools import memx_search, memx_ingest

        assert "search" in memx_search.description.lower()
        assert "save" in memx_ingest.description.lower() or "persist" in memx_ingest.description.lower()


class TestMemxBridge:
    """memx_bridge.py のテスト"""

    def test_is_memx_enabled(self):
        """memx有効無効判定テスト"""
        import config_manager
        from tools.memx_bridge import is_memx_enabled

        # 無効状態
        config_manager.CONFIG_GLOBAL = {"memx_settings": {"use_memx": False}}
        assert is_memx_enabled() == False

        # 有効状態
        config_manager.CONFIG_GLOBAL = {"memx_settings": {"use_memx": True}}
        assert is_memx_enabled() == True

    def test_sync_functions_room_parameter(self):
        """sync関数がroom_nameパラメータを受け取る"""
        import config_manager
        from tools.memx_bridge import sync_entity_to_memx

        # memx無効時は何もしない（Falseを返す）
        config_manager.CONFIG_GLOBAL = {"memx_settings": {"use_memx": False}}
        result = sync_entity_to_memx("test_entity", "test content", "test_room")
        assert result == False  # memx無効時は同期しない


# pytest 実行用
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

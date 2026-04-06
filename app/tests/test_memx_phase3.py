# tests/test_memx_phase3.py
"""
memx-resolver Phase 3 Acceptance Tests

要件書 docs/MEMX_INTEGRATION_REQUIREMENTS.md の AC-P3-001〜AC-P3-010 に基づく受け入れテスト。

テスト構成:
1. Unit Tests (Mock): 縮退制御、移行判断ロジックの検証（Mock使用）
2. LocalAdapter Tests: use_memx=false での動作検証（常に実行可能）
3. Real API Tests: MemxAdapter + 実 memx-resolver API 経由の検証（サーバー起動時のみ）

AC-P3-001〜010 対応:
- AC-P3-001: 縮退対象の無効化/read-only化 (Unit)
- AC-P3-002: 参照・移行補助・ロールバック経路維持 (LocalAdapter)
- AC-P3-003: 完全移行判断の記録 (Unit)
- AC-P3-004: Phase 2 検証結果の反映 (Real API)
- AC-P3-005: 高度 resolver の明示的有効化 (Unit)
- AC-P3-006: 高度 resolver 失敗時の退避 (Unit)
- AC-P3-007: ロールバック手順の存在と再現確認 (LocalAdapter)
- AC-P3-008: room 単位の移行状態追跡 (LocalAdapter)
- AC-P3-009: 移行案内の存在 (Unit)
- AC-P3-010: 対象外 room/データの保護 (LocalAdapter)
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


# ===== Unit Tests (Mock使用) =====

class TestPhase3Unit:
    """
    Phase 3 のロジック検証（Mock使用）。
    設定、縮退制御、移行判断のロジックをテスト。
    """

    # --- AC-P3-001: 縮退対象の無効化/read-only化 ---
    def test_ac_p3_001_deprecation_control(self, local_adapter_config):
        """
        AC-P3-001: 縮退対象として定義された旧記憶導線が、
        設定または明示手順に従って無効化または read-only 化できる

        検証: 縮退制御 API が動作すること
        または: 全縮退候補が削除済みであること
        """
        from tools.memx_phase3 import (
            get_deprecation_status,
            set_deprecation_status,
            is_component_read_only,
            is_component_disabled,
            DEPRECATION_TARGETS,
            DELETED_COMPONENTS
        )

        # 縮退対象がない（全削除完了）場合は、削除履歴があることを確認
        if len(DEPRECATION_TARGETS) == 0:
            # 全削除完了状態 - 削除履歴が存在することを確認
            assert len(DELETED_COMPONENTS) > 0, "No active targets and no deletion history"
            return

        # 縮退対象がある場合は制御 API をテスト
        # 現在の状態を取得
        status = get_deprecation_status()
        assert isinstance(status, dict)

        # read-only 設定をテスト（read_only に対応しているコンポーネント）
        for name, info in DEPRECATION_TARGETS.items():
            if info["read_only_mode_available"]:
                result = set_deprecation_status(name, "read_only")
                assert "error" not in result, f"Failed to set {name} to read_only: {result}"

                assert is_component_read_only(name)

        # disabled 設定をテスト
        for name, info in DEPRECATION_TARGETS.items():
            if info["can_disable"]:
                result = set_deprecation_status(name, "disabled")
                assert "error" not in result, f"Failed to disable {name}: {result}"

                assert is_component_disabled(name)

    def test_deprecation_targets_defined(self, local_adapter_config):
        """
        縮退対象と存続対象が明確に定義されている

        縮退対象がない（全削除完了）場合は、削除履歴が存在することを確認
        """
        from tools.memx_phase3 import DEPRECATION_TARGETS, SURVIVING_COMPONENTS, DELETED_COMPONENTS

        # 縮退対象がある場合は必須フィールド確認
        if len(DEPRECATION_TARGETS) > 0:
            required_fields = ["description", "memx_replacement", "can_disable",
                              "read_only_mode_available", "rollback_supported", "status"]
            for name, info in DEPRECATION_TARGETS.items():
                for field in required_fields:
                    assert field in info, f"{name} missing field: {field}"

        # 縮退対象がない場合は削除履歴を確認
        else:
            assert len(DELETED_COMPONENTS) > 0, "No active targets and no deletion history"
            # 削除履歴の必須フィールド確認
            deleted_required = ["description", "memx_replacement", "deleted_at"]
            for name, info in DELETED_COMPONENTS.items():
                for field in deleted_required:
                    assert field in info, f"{name} missing field: {field}"

        # 存続対象の確認
        assert len(SURVIVING_COMPONENTS) > 0
        for name, info in SURVIVING_COMPONENTS.items():
            assert "description" in info
            assert "reason" in info

    # --- AC-P3-003: 完全移行判断の記録 ---
    def test_ac_p3_003_migration_judgment(self, local_adapter_config, workspace_tmp_path):
        """
        AC-P3-003: 完全移行判断が、検証結果と理由を伴って
        `移行可` / `暫定並行運用` / `移行不可` のいずれかで記録される

        検証: 移行判断 API が3状態のいずれかを返すこと
        """
        from tools.memx_phase3 import judge_migration_status, MigrationJudgment

        judgment = judge_migration_status("test_room")

        # 正しい型であること
        assert isinstance(judgment, MigrationJudgment)

        # 判定が3状態のいずれかであること
        assert judgment.verdict in ["移行可", "暫定並行運用", "移行不可"]

        # 理由が記録されていること
        assert len(judgment.reasons) > 0

        # 検証結果が記録されていること
        assert len(judgment.verification_results) > 0

        # to_dict が動作すること
        judgment_dict = judgment.to_dict()
        assert "verdict" in judgment_dict
        assert "reasons" in judgment_dict
        assert "verification_results" in judgment_dict

    # --- AC-P3-005: 高度 resolver の明示的有効化 ---
    def test_ac_p3_005_advanced_resolver_disabled_by_default(self, local_adapter_config):
        """
        AC-P3-005: 高度 resolver 機能は、明示的な有効化条件の下でのみ利用可能になる

        検証: デフォルトで無効であること
        """
        from tools.memx_phase3 import is_advanced_resolver_enabled

        # デフォルトで無効
        assert is_advanced_resolver_enabled() is False

    def test_advanced_resolver_enable_explicitly(self, local_adapter_config):
        """明示的に有効化した場合のみ有効になる"""
        from tools.memx_phase3 import (
            is_advanced_resolver_enabled,
            enable_advanced_resolver
        )

        # 有効化
        result = enable_advanced_resolver(True, reason="test_enable")
        assert result["advanced_resolver_enabled"] is True

        # 有効化後は True
        assert is_advanced_resolver_enabled() is True

        # 無効化
        result = enable_advanced_resolver(False, reason="test_disable")
        assert result["advanced_resolver_enabled"] is False

        # 無効化後は False
        assert is_advanced_resolver_enabled() is False

    # --- AC-P3-006: 高度 resolver 失敗時の退避 ---
    def test_ac_p3_006_advanced_resolver_fallback(self, local_adapter_config):
        """
        AC-P3-006: 高度 resolver 機能の失敗時に、Phase 2 水準の基本導線へ退避できる

        検証: safe_advanced_resolver_call がフォールバックすること
        """
        from tools.memx_phase3 import safe_advanced_resolver_call, enable_advanced_resolver

        # 高度機能（失敗する）
        def advanced_func():
            raise RuntimeError("Advanced feature failed")

        # フォールバック（成功する）
        def fallback_func():
            return "fallback_result"

        # 無効時は常にフォールバック
        result = safe_advanced_resolver_call(advanced_func, fallback_func)
        assert result == "fallback_result"

        # 有効化しても例外時はフォールバック
        enable_advanced_resolver(True)
        result = safe_advanced_resolver_call(advanced_func, fallback_func)
        assert result == "fallback_result"

        # 後始末：無効化
        enable_advanced_resolver(False)

    # --- AC-P3-009: 移行案内の存在 ---
    def test_ac_p3_009_migration_guide_exists(self, local_adapter_config):
        """
        AC-P3-009: 既存利用者向けに、設定変更点、互換性差分、復旧手順を含む移行案内が存在する

        検証: 移行案内が取得できること
        """
        from tools.memx_phase3 import get_migration_guide

        guide = get_migration_guide()

        # 必要なセクションが存在すること
        assert "title" in guide
        assert "settings" in guide
        assert "compatibility" in guide
        assert "rollback" in guide

        # 設定説明が含まれていること
        assert "use_memx" in guide["settings"]
        assert "gc_execute_enabled" in guide["settings"]
        assert "phase3_settings" in guide["settings"]

        # ロールバック手順が含まれていること
        assert "steps" in guide["rollback"]
        assert len(guide["rollback"]["steps"]) > 0


# ===== LocalAdapter Tests (常に実行可能) =====

@pytest.mark.llm_mock
class TestPhase3LocalAdapter:
    """
    LocalAdapter 使用時の Phase 3 動作検証。
    use_memx=false での動作を確認。

    NOTE: LLM/UI依存あり (entity_tools, memory_tools -> langchain, memory_manager -> gradio)
    """

    @pytest.fixture(autouse=True)
    def setup(self, local_adapter_config):
        pass

    # --- AC-P3-002: 参照・移行補助・ロールバック経路維持 ---
    def test_ac_p3_002_rollback_paths_preserved(self, workspace_tmp_path):
        """
        AC-P3-002: 旧実装縮退後も、必要な参照・移行補助・ロールバックに
        必要な最低限の経路が維持される

        検証: LocalAdapter と移行ツールが使用可能であること
        """
        from adapters import get_memory_adapter
        from adapters.local_adapter import LocalAdapter
        from tools.memx_migrate import migrate_preview

        # LocalAdapter が使用可能
        adapter = get_memory_adapter("test_room")
        # クラス名で確認（モジュール再読み込みの問題を回避）
        assert type(adapter).__name__ == "LocalAdapter"
        assert adapter.is_available()

        # 移行プレビューが動作する
        result = migrate_preview(
            source="entity_memory",
            room_name="test_room",
            target_store="knowledge"
        )
        assert result is not None

    def test_surviving_components_available(self):
        """存続コンポーネントが利用可能であること"""
        from tools.memx_phase3 import SURVIVING_COMPONENTS

        for name in SURVIVING_COMPONENTS:
            if name == "local_adapter":
                from adapters.local_adapter import LocalAdapter
                assert LocalAdapter is not None
            elif name == "entity_tools":
                # entity_tools モジュールが存在し、関数があることを確認
                from tools.entity_tools import read_entity_memory, write_entity_memory
                assert read_entity_memory is not None
            elif name == "memory_tools":
                # memory_tools モジュールが存在し、関数があることを確認
                from tools.memory_tools import recall_memories, search_memory
                assert recall_memories is not None
            elif name == "memory_manager":
                # memory_manager モジュールが存在し、関数があることを確認
                from memory_manager import save_memory_data, load_memory_data_safe
                assert save_memory_data is not None

    # --- AC-P3-007: ロールバック手順の存在と再現確認 ---
    def test_ac_p3_007_rollback_procedure(self, workspace_tmp_path):
        """
        AC-P3-007: 旧構成へのロールバック手順が存在し、
        少なくとも 1 回は再現確認されている

        検証: ロールバック状態確認と実行が可能であること
        """
        from tools.memx_phase3 import get_rollback_status, execute_rollback

        # テスト用 room にデータを作成
        room_name = "rollback_test"
        room_dir = workspace_tmp_path / "characters" / room_name
        entities_dir = room_dir / "memory" / "entities"
        entities_dir.mkdir(parents=True)
        test_entity = entities_dir / "test.md"
        test_entity.write_text("# Test Entity", encoding="utf-8")

        # ロールバック状態確認
        status = get_rollback_status(room_name)

        # 状態が取得できること
        assert "rollback_possible" in status
        assert "steps" in status

        # ロールバックが可能であること（必要コンポーネントが存在すること）
        assert status["rollback_possible"] is True, \
            f"Rollback not possible: missing={status.get('missing_components', [])}"

        # ローカルデータが存在すること
        assert status["local_data_intact"] is True

        # ロールバック実行
        result = execute_rollback(room_name)

        # 成功すること
        assert result["success"] is True, f"Rollback failed: {result}"
        assert result["new_use_memx"] is False

        # ローカルデータが維持されていること
        assert test_entity.exists()

    # --- AC-P3-008: room 単位の移行状態追跡 ---
    def test_ac_p3_008_room_migration_tracking(self, workspace_tmp_path):
        """
        AC-P3-008: room 単位のデータ保全状態と移行状態が追跡可能である

        検証: 移行判断履歴が room 単位で保存されること
        """
        from tools.memx_phase3 import (
            judge_migration_status,
            get_migration_history
        )

        room_name = "tracking_test"

        # 移行判断を実行
        judgment = judge_migration_status(room_name)

        # 履歴を取得
        history = get_migration_history(room_name)

        # 履歴が記録されていること
        assert len(history) > 0

        # 最新の履歴が今の判断と一致すること
        latest = history[-1]
        assert latest["verdict"] == judgment.verdict

    # --- AC-P3-010: 対象外 room/データの保護 ---
    def test_ac_p3_010_data_protection(self, workspace_tmp_path):
        """
        AC-P3-010: Phase 3 実施後も、明示対象外の room や既存データが破壊されていない

        検証: 他 room のデータに影響しないこと
        """
        from tools.memx_phase3 import (
            set_deprecation_status,
            judge_migration_status,
            execute_rollback
        )

        # 2つの room を作成
        room_a = "protection_a"
        room_b = "protection_b"

        for room_name in [room_a, room_b]:
            room_dir = workspace_tmp_path / "characters" / room_name
            entities_dir = room_dir / "memory" / "entities"
            entities_dir.mkdir(parents=True)
            entity_file = entities_dir / f"{room_name}_entity.md"
            entity_file.write_text(f"# {room_name} Entity", encoding="utf-8")

        # room_a で操作を実行
        set_deprecation_status("entity_memory_manager", "deprecated")
        judge_migration_status(room_a)
        result = execute_rollback(room_a)

        # room_b のデータが影響を受けていないこと
        room_b_entity = workspace_tmp_path / "characters" / room_b / "memory" / "entities" / f"{room_b}_entity.md"
        assert room_b_entity.exists()
        content = room_b_entity.read_text(encoding="utf-8")
        assert room_b in content

    def test_local_data_not_deleted(self, workspace_tmp_path):
        """ローカルデータが削除されないこと"""
        room_name = "data_preserve_test"
        room_dir = workspace_tmp_path / "characters" / room_name
        entities_dir = room_dir / "memory" / "entities"
        entities_dir.mkdir(parents=True)

        test_entity = entities_dir / "important.md"
        test_entity.write_text("# Important Entity\nThis should not be deleted.", encoding="utf-8")

        from tools.memx_phase3 import (
            set_deprecation_status,
            judge_migration_status,
            execute_rollback
        )

        # 各種操作を実行
        set_deprecation_status("entity_memory_manager", "read_only")
        judge_migration_status(room_name)
        execute_rollback(room_name)

        # ファイルが存在すること
        assert test_entity.exists()

        # 内容が変更されていないこと
        content = test_entity.read_text(encoding="utf-8")
        assert "Important Entity" in content


# ===== Real API Tests (MemxAdapter到達時のみ実行) =====

class TestPhase3RealAPI:
    """
    実 memx-resolver API 使用時の Phase 3 検証。
    memx_server_available=False の場合はスキップされる。
    """

    @pytest.fixture(autouse=True)
    def setup(self, real_api_config, memx_server_available):
        if not memx_server_available:
            pytest.skip("memx-resolver API not available at http://127.0.0.1:7766")

    # --- AC-P3-004: Phase 2 検証結果の反映 ---
    def test_ac_p3_004_phase2_results_reflected(self):
        """
        AC-P3-004: 完全移行判断に、Phase 2 の Real API 検証結果と
        fallback 検証結果が反映されている

        検証: MemxAdapter 使用時に移行判断が反映されること
        """
        from tools.memx_phase3 import judge_migration_status, verify_phase2_requirements
        from adapters import get_memory_adapter, MemxAdapter

        # MemxAdapter が使用されていることを確認
        adapter = get_memory_adapter("api_test_room")
        assert isinstance(adapter, MemxAdapter), "Expected MemxAdapter"

        # Phase 2 検証を実行
        results = verify_phase2_requirements()

        # 検証結果が返されること
        assert len(results) > 0

        # 各結果が VerificationResult であること
        for r in results:
            assert hasattr(r, "name")
            assert hasattr(r, "passed")
            assert hasattr(r, "details")

        # 移行判断を実行
        judgment = judge_migration_status("api_test_room")

        # 判断に検証結果が反映されていること
        assert len(judgment.verification_results) > 0

        # MemxAdapter 到達確認が含まれていること
        reasons_str = " ".join(judgment.reasons)
        assert "MemxAdapter" in reasons_str or judgment.verdict == "移行可"


# ===== pytest 実行用 =====

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
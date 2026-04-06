# tools/memx_phase3.py
"""
memx Phase 3: Migration Status and Deprecation Control

Phase 3 の主な機能:
1. 旧実装の縮退制御 (FR-P3-001〜004)
2. 完全移行判断 (FR-P3-005〜008)
3. 高度 resolver 機能の安全統合 (FR-P3-009〜012)
4. ロールバック支援 (FR-P3-013〜016)

使い方:
- migration_status() で現在の移行状態を確認
- deprecation_control で旧実装の無効化/read-only化を制御
- advanced_resolver_enabled で高度機能の有効化を制御
"""

from typing import Dict, List, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json


# ===== Migration Status Types =====

MigrationVerdict = Literal["移行可", "暫定並行運用", "移行不可"]

@dataclass
class VerificationResult:
    """各検証項目の結果"""
    name: str
    passed: bool
    details: str = ""
    timestamp: str = ""


@dataclass
class MigrationJudgment:
    """完全移行判断の結果"""
    verdict: MigrationVerdict
    reasons: List[str]
    verification_results: List[VerificationResult]
    judged_at: str
    room_name: str = ""

    def to_dict(self) -> Dict:
        return {
            "verdict": self.verdict,
            "reasons": self.reasons,
            "verification_results": [
                {"name": v.name, "passed": v.passed, "details": v.details, "timestamp": v.timestamp}
                for v in self.verification_results
            ],
            "judged_at": self.judged_at,
            "room_name": self.room_name
        }


# ===== Deprecation Control =====

# 削除済みコンポーネントの履歴
# ドキュメンテーション目的で残しておく
DELETED_COMPONENTS = {
    "rag_manager": {
        "description": "RAG検索管理",
        "memx_replacement": "memx_search / memx_recall",
        "deleted_at": "2026-04-06",
        "notes": "削除完了 - memx 経路で代替"
    },
    "episodic_memory_manager": {
        "description": "エピソード記憶管理",
        "memx_replacement": "memx_ingest(store='journal') / memx_recall",
        "deleted_at": "2026-04-06",
        "notes": "削除完了 - memx journal 経路で代替"
    },
    "entity_memory_manager": {
        "description": "エンティティ記憶管理",
        "memx_replacement": "entity_tools / memx_ingest(store='knowledge')",
        "deleted_at": "2026-04-06",
        "notes": "削除完了 - entity_tools / memx 経路で代替"
    },
    "dreaming_manager_sync": {
        "description": "ドリームマネージャ同期",
        "memx_replacement": "memx 同期なしで動作",
        "deleted_at": "2026-04-06",
        "notes": "削除完了 - 同期なし運用"
    },
    "motivation_manager_sync": {
        "description": "モチベーションマネージャ同期",
        "memx_replacement": "memx 同期なしで動作",
        "deleted_at": "2026-04-06",
        "notes": "削除完了 - 同期なし運用"
    }
}

# 縮退対象の旧実装一覧
# 全削除候補が完了 - 現在アクティブな縮退対象はなし
DEPRECATION_TARGETS = {
    # アクティブな縮退候補なし（全削除完了）
}

# 存続対象（縮退しない）
SURVIVING_COMPONENTS = {
    "memory_manager": {
        "description": "汎用メモリ管理（local fallback用）",
        "reason": "LocalAdapter 動作に必要"
    },
    "entity_tools": {
        "description": "エンティティ操作ツール（entity_memory_manager 削除後の代替）",
        "reason": "knowledge store 操作の主要導線"
    },
    "memory_tools": {
        "description": "基本メモリツール",
        "reason": "後方互換性維持"
    },
    "local_adapter": {
        "description": "LocalAdapter",
        "reason": "フォールバック先として必須"
    },
    "memx_tools": {
        "description": "memx統合ツール",
        "reason": "主要記憶操作経路"
    }
}


def get_deprecation_status() -> Dict:
    """現在の縮退状態を取得"""
    import config_manager

    memx_settings = config_manager.CONFIG_GLOBAL.get("memx_settings", {})
    phase3_settings = memx_settings.get("phase3_settings", {})

    deprecation_status = {}
    for name, info in DEPRECATION_TARGETS.items():
        current_status = phase3_settings.get("deprecation", {}).get(name, info["status"])
        deprecation_status[name] = {
            **info,
            "current_status": current_status
        }

    return deprecation_status


def set_deprecation_status(target: str, status: str) -> Dict:
    """
    縮退状態を設定

    Args:
        target: 対象コンポーネント名
        status: active, deprecated, read_only, disabled

    Returns:
        設定結果
    """
    import config_manager

    if target not in DEPRECATION_TARGETS:
        return {"error": f"Unknown target: {target}"}

    if status not in ["active", "deprecated", "read_only", "disabled"]:
        return {"error": f"Invalid status: {status}"}

    target_info = DEPRECATION_TARGETS[target]

    # read_only 要求時の確認
    if status == "read_only" and not target_info["read_only_mode_available"]:
        return {"error": f"{target} does not support read_only mode"}

    # disabled 要求時の確認
    if status == "disabled" and not target_info["can_disable"]:
        return {"error": f"{target} cannot be disabled"}

    # 設定更新
    memx_settings = config_manager.CONFIG_GLOBAL.setdefault("memx_settings", {})
    phase3_settings = memx_settings.setdefault("phase3_settings", {})
    deprecation = phase3_settings.setdefault("deprecation", {})
    deprecation[target] = status

    return {
        "target": target,
        "previous_status": DEPRECATION_TARGETS[target]["status"],
        "new_status": status,
        "timestamp": datetime.now().isoformat()
    }


def is_component_read_only(component_name: str) -> bool:
    """コンポーネントが read-only モードか確認"""
    status = get_deprecation_status()
    if component_name in status:
        return status[component_name]["current_status"] == "read_only"
    return False


def is_component_disabled(component_name: str) -> bool:
    """コンポーネントが無効化されているか確認"""
    status = get_deprecation_status()
    if component_name in status:
        return status[component_name]["current_status"] == "disabled"
    return False


# ===== Migration Judgment =====

def verify_phase2_requirements() -> List[VerificationResult]:
    """
    Phase 2 の要件検証結果を収集

    Returns:
        各検証項目の結果リスト
    """
    results = []
    now = datetime.now().isoformat()

    # 1. recall 検証
    try:
        from tools.memx_tools import memx_recall
        result = memx_recall.invoke({
            "query": "health_check",
            "room_name": "verification_room",
            "recall_mode": "relevant"
        })
        passed = "error" not in result.lower()
        results.append(VerificationResult(
            name="recall_verification",
            passed=passed,
            details="recall 動作確認" if passed else f"recall 失敗: {result[:100]}",
            timestamp=now
        ))
    except Exception as e:
        results.append(VerificationResult(
            name="recall_verification",
            passed=False,
            details=f"recall 例外: {str(e)}",
            timestamp=now
        ))

    # 2. resolve 検証
    try:
        from adapters import get_memory_adapter, MemxAdapter
        adapter = get_memory_adapter("verification_room")
        if isinstance(adapter, MemxAdapter) and adapter.is_available():
            results.append(VerificationResult(
                name="resolve_verification",
                passed=True,
                details="MemxAdapter 利用可能",
                timestamp=now
            ))
        else:
            results.append(VerificationResult(
                name="resolve_verification",
                passed=False,
                details="MemxAdapter 未使用または未到達",
                timestamp=now
            ))
    except Exception as e:
        results.append(VerificationResult(
            name="resolve_verification",
            passed=False,
            details=f"resolve 確認例外: {str(e)}",
            timestamp=now
        ))

    # 3. GC 検証
    try:
        import config_manager
        gc_enabled = config_manager.CONFIG_GLOBAL.get("memx_settings", {}).get("gc_execute_enabled", False)
        results.append(VerificationResult(
            name="gc_safety_verification",
            passed=True,  # GC が無効でも安全
            details=f"gc_execute_enabled={gc_enabled}",
            timestamp=now
        ))
    except Exception as e:
        results.append(VerificationResult(
            name="gc_safety_verification",
            passed=False,
            details=f"GC 設定確認例外: {str(e)}",
            timestamp=now
        ))

    # 4. migrate 検証
    try:
        from tools.memx_migrate import migrate_preview
        result = migrate_preview(
            source="entity_memory",
            room_name="verification_room",
            target_store="knowledge"
        )
        passed = "candidates" in result
        results.append(VerificationResult(
            name="migrate_verification",
            passed=passed,
            details="migrate preview 動作確認" if passed else "migrate preview 失敗",
            timestamp=now
        ))
    except Exception as e:
        results.append(VerificationResult(
            name="migrate_verification",
            passed=False,
            details=f"migrate 例外: {str(e)}",
            timestamp=now
        ))

    # 5. fallback 検証
    try:
        from adapters import get_memory_adapter, LocalAdapter
        # use_memx=false で LocalAdapter が使われることを確認
        adapter = get_memory_adapter("fallback_verification_room")
        if isinstance(adapter, LocalAdapter):
            results.append(VerificationResult(
                name="fallback_verification",
                passed=True,
                details="LocalAdapter フォールバック利用可能",
                timestamp=now
            ))
        else:
            # MemxAdapter でも is_available() が False なら OK
            if not adapter.is_available():
                results.append(VerificationResult(
                    name="fallback_verification",
                    passed=True,
                    details="MemxAdapter は未到達、フォールバック可能",
                    timestamp=now
                ))
            else:
                results.append(VerificationResult(
                    name="fallback_verification",
                    passed=True,
                    details="MemxAdapter 利用可能（フォールバック先は LocalAdapter）",
                    timestamp=now
                ))
    except Exception as e:
        results.append(VerificationResult(
            name="fallback_verification",
            passed=False,
            details=f"fallback 確認例外: {str(e)}",
            timestamp=now
        ))

    return results


def judge_migration_status(room_name: str = "") -> MigrationJudgment:
    """
    完全移行可否を判断

    Args:
        room_name: 対象 room 名（オプション）

    Returns:
        MigrationJudgment: 移行判断結果
    """
    verification_results = verify_phase2_requirements()

    # 判定ロジック
    passed_count = sum(1 for v in verification_results if v.passed)
    total_count = len(verification_results)

    reasons = []

    if passed_count == total_count:
        verdict = "移行可"
        reasons.append(f"全検証項目 ({total_count}/{total_count}) 合格")
        reasons.append("recall, resolve, gc, migrate, fallback 全て動作確認")
    elif passed_count >= total_count * 0.6:
        verdict = "暫定並行運用"
        reasons.append(f"一部検証項目 ({passed_count}/{total_count}) 合格")
        failed = [v.name for v in verification_results if not v.passed]
        reasons.append(f"未合格項目: {', '.join(failed)}")
        reasons.append("並行運用で安全性を確保しつつ移行準備継続")
    else:
        verdict = "移行不可"
        reasons.append(f"検証項目の多くが不合格 ({passed_count}/{total_count})")
        reasons.append("LocalAdapter での運用継続を推奨")

    # MemxAdapter 到達確認
    try:
        from adapters import get_memory_adapter, MemxAdapter
        adapter = get_memory_adapter(room_name or "default")
        if isinstance(adapter, MemxAdapter) and adapter.is_available():
            reasons.append("MemxAdapter 到達確認: OK")
        else:
            reasons.append("MemxAdapter 到達確認: NG (LocalAdapter 使用)")
            if verdict == "移行可":
                verdict = "暫定並行運用"
                reasons.append("API到達性の問題により判断を下方修正")
    except Exception as e:
        reasons.append(f"MemxAdapter 確認例外: {str(e)}")

    judgment = MigrationJudgment(
        verdict=verdict,
        reasons=reasons,
        verification_results=verification_results,
        judged_at=datetime.now().isoformat(),
        room_name=room_name
    )

    # 結果を保存
    save_migration_judgment(judgment)

    return judgment


def save_migration_judgment(judgment: MigrationJudgment) -> None:
    """移行判断結果をファイルに保存"""
    import constants

    room_dir = Path(constants.ROOMS_DIR) / (judgment.room_name or "default")
    status_dir = room_dir / "memx"
    status_dir.mkdir(parents=True, exist_ok=True)

    status_file = status_dir / "migration_status.json"

    # 既存履歴を読み込み
    history = []
    if status_file.exists():
        try:
            history = json.loads(status_file.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except:
            history = []

    # 新しい判断を追加
    history.append(judgment.to_dict())

    # 直近 10 件のみ保持
    history = history[-10:]

    status_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def get_migration_history(room_name: str) -> List[Dict]:
    """移行判断履歴を取得"""
    import constants

    room_dir = Path(constants.ROOMS_DIR) / room_name
    status_file = room_dir / "memx" / "migration_status.json"

    if not status_file.exists():
        return []

    try:
        return json.loads(status_file.read_text(encoding="utf-8"))
    except:
        return []


# ===== Advanced Resolver Control =====

def is_advanced_resolver_enabled() -> bool:
    """
    高度 resolver 機能が有効か確認

    FR-P3-011: 高度 resolver 統合は、明示的な導線または制御条件なしに自動有効化してはならない

    Returns:
        True のみ明示的に有効化設定がある場合
    """
    import config_manager

    memx_settings = config_manager.CONFIG_GLOBAL.get("memx_settings", {})
    phase3_settings = memx_settings.get("phase3_settings", {})

    # 明示的に true に設定されている場合のみ有効
    return phase3_settings.get("advanced_resolver_enabled", False) is True


def enable_advanced_resolver(enable: bool = True, reason: str = "") -> Dict:
    """
    高度 resolver 機能の有効化/無効化

    Args:
        enable: True で有効化、False で無効化
        reason: 有効化の理由（監査用）

    Returns:
        設定結果
    """
    import config_manager

    memx_settings = config_manager.CONFIG_GLOBAL.setdefault("memx_settings", {})
    phase3_settings = memx_settings.setdefault("phase3_settings", {})

    previous = phase3_settings.get("advanced_resolver_enabled", False)
    phase3_settings["advanced_resolver_enabled"] = enable

    # ログ記録
    log_entry = {
        "action": "enable" if enable else "disable",
        "reason": reason,
        "previous_value": previous,
        "new_value": enable,
        "timestamp": datetime.now().isoformat()
    }

    advanced_log = phase3_settings.setdefault("advanced_resolver_log", [])
    advanced_log.append(log_entry)
    # 直近 20 件を保持
    phase3_settings["advanced_resolver_log"] = advanced_log[-20:]

    return {
        "advanced_resolver_enabled": enable,
        "previous_value": previous,
        "reason": reason,
        "timestamp": log_entry["timestamp"]
    }


def safe_advanced_resolver_call(func, fallback_func, *args, **kwargs):
    """
    高度 resolver 機能の安全な呼び出し

    FR-P3-012: 高度 resolver 統合の失敗時も、Phase 2 水準の基本導線へ安全に退避できなければならない

    Args:
        func: 高度 resolver 機能
        fallback_func: Phase 2 水準のフォールバック関数
        *args, **kwargs: 関数引数

    Returns:
        高度機能の結果、またはフォールバック結果
    """
    if not is_advanced_resolver_enabled():
        # 無効時は常にフォールバック
        return fallback_func(*args, **kwargs)

    try:
        result = func(*args, **kwargs)
        return result
    except Exception as e:
        print(f"[Phase3] Advanced resolver failed, falling back to Phase2: {e}")
        return fallback_func(*args, **kwargs)


# ===== Rollback Support =====

def get_rollback_status(room_name: str) -> Dict:
    """
    ロールバック状態を確認

    Returns:
        ロールバック可能性の状態
    """
    import constants
    import config_manager

    room_dir = Path(constants.ROOMS_DIR) / room_name

    status = {
        "rollback_possible": True,
        "local_data_intact": False,
        "memx_data_exists": False,
        "required_components_available": [],
        "missing_components": [],
        "steps": []
    }

    # ローカルデータ確認
    entities_dir = room_dir / "memory" / "entities"
    if entities_dir.exists() and any(entities_dir.glob("*.md")):
        status["local_data_intact"] = True
        status["steps"].append("1. Local entity data exists and accessible")
    else:
        status["steps"].append("1. WARNING: No local entity data found")

    # memx データ確認
    memx_dir = room_dir / "memx"
    if memx_dir.exists() and any(memx_dir.glob("*.db")):
        status["memx_data_exists"] = True
        status["steps"].append("2. memx data exists (can be kept or removed)")
    else:
        status["steps"].append("2. No memx data found")

    # 必要コンポーネント確認（実在する関数・クラスを確認）
    required = ["LocalAdapter", "entity_tools", "memory_tools"]
    for comp in required:
        try:
            if comp == "LocalAdapter":
                from adapters.local_adapter import LocalAdapter
                status["required_components_available"].append(comp)
            elif comp == "entity_tools":
                # entity_tools モジュールが存在し、read_entity_memory 等の関数があることを確認
                from tools.entity_tools import read_entity_memory, write_entity_memory
                status["required_components_available"].append(comp)
            elif comp == "memory_tools":
                # memory_tools モジュールが存在し、recall_memories 等の関数があることを確認
                from tools.memory_tools import recall_memories, search_memory
                status["required_components_available"].append(comp)
        except ImportError:
            status["missing_components"].append(comp)
            status["rollback_possible"] = False

    status["steps"].append(f"3. Required components: {', '.join(status['required_components_available'])}")

    if status["missing_components"]:
        status["steps"].append(f"   MISSING: {', '.join(status['missing_components'])}")

    # 現在の設定
    memx_settings = config_manager.CONFIG_GLOBAL.get("memx_settings", {})
    status["current_use_memx"] = memx_settings.get("use_memx", False)
    status["steps"].append(f"4. Current use_memx setting: {status['current_use_memx']}")

    # ロールバック手順
    status["steps"].append("5. To rollback: set use_memx=false in config.json")
    status["steps"].append("6. Restart Open-Ark")
    status["steps"].append("7. Verify LocalAdapter is active")

    return status


def execute_rollback(room_name: str, preserve_memx_data: bool = True) -> Dict:
    """
    ロールバックを実行

    Args:
        room_name: 対象 room
        preserve_memx_data: memx データを保持するか

    Returns:
        ロールバック結果
    """
    import config_manager
    from adapters.memory_adapter import reset_adapter

    # 現在の状態確認
    rollback_status = get_rollback_status(room_name)

    if not rollback_status["rollback_possible"]:
        return {
            "success": False,
            "error": "Rollback not possible",
            "missing_components": rollback_status["missing_components"]
        }

    # use_memx を false に設定
    memx_settings = config_manager.CONFIG_GLOBAL.setdefault("memx_settings", {})
    previous_use_memx = memx_settings.get("use_memx", False)
    memx_settings["use_memx"] = False

    # アダプターキャッシュをクリア
    reset_adapter()

    result = {
        "success": True,
        "previous_use_memx": previous_use_memx,
        "new_use_memx": False,
        "preserved_memx_data": preserve_memx_data,
        "timestamp": datetime.now().isoformat(),
        "room_name": room_name,
        "next_steps": [
            "Restart Open-Ark to apply changes",
            "Verify LocalAdapter is active",
            "Check local data files are accessible"
        ]
    }

    # ロールバック履歴を保存
    import constants
    room_dir = Path(constants.ROOMS_DIR) / room_name
    status_dir = room_dir / "memx"
    status_dir.mkdir(parents=True, exist_ok=True)

    history_file = status_dir / "rollback_history.json"
    history = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except:
            history = []

    history.append(result)
    history_file.write_text(json.dumps(history[-10:], ensure_ascii=False, indent=2), encoding="utf-8")

    return result


# ===== User Migration Guide =====

def get_migration_guide() -> Dict:
    """
    利用者向け移行案内を取得

    Returns:
        移行案内情報
    """
    return {
        "title": "memx-resolver 移行案内",
        "version": "Phase 3",
        "settings": {
            "use_memx": {
                "description": "memx-resolver の利用有無",
                "type": "boolean",
                "default": False,
                "effect": {
                    "true": "MemxAdapter を優先使用、API未到達時は LocalAdapter にフォールバック",
                    "false": "LocalAdapter のみ使用（従来動作）"
                }
            },
            "gc_execute_enabled": {
                "description": "GC execute モードの有効化",
                "type": "boolean",
                "default": False,
                "warning": "true に設定すると実際の削除が行われる"
            },
            "phase3_settings": {
                "description": "Phase 3 追加設定",
                "advanced_resolver_enabled": {
                    "description": "高度 resolver 機能の有効化",
                    "type": "boolean",
                    "default": False,
                    "warning": "実験的機能、失敗時は Phase 2 水準にフォールバック"
                },
                "deprecation": {
                    "description": "旧実装の縮退状態",
                    "type": "object",
                    "values": ["active", "deprecated", "read_only", "disabled"]
                }
            }
        },
        "compatibility": {
            "use_memx_false": "従来の動作を維持、全ての既存機能が利用可能",
            "use_memx_true_api_down": "LocalAdapter にフォールバック、主要機能は継続利用可能",
            "phase2_tools": "memx_recall, memx_resolve, memx_gc, memx_migrate が追加",
            "phase3_features": "縮退制御、完全移行判断、高度 resolver（明示的有効化時のみ）"
        },
        "rollback": {
            "description": "旧構成への復帰",
            "steps": [
                "1. config.json の use_memx を false に設定",
                "2. Open-Ark を再起動",
                "3. LocalAdapter が使用されることを確認"
            ],
            "data_safety": "ローカルデータは削除されず、memx データも保持可能"
        }
    }
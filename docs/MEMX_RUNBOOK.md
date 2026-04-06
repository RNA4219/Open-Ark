# memx-resolver 統合 Runbook

## 1. 目的

本 Runbook は、Open-Ark から `memx-resolver` を利用する際の起動確認、疎通確認、障害切り分け、段階移行の手順をまとめたものである。  
Windows 環境を主導線とし、Phase 1〜3 の実装結果に基づく運用手順を定義する。

---

## 2. 前提

- Open-Ark の設定ファイルは `app/config.json`
- room データは `app/characters/<room_name>/...`
- memx の room ごとの DB 配置既定は `app/characters/<room_name>/memx`

---

## 3. 日常運用

### 3.1 memx-resolver API 起動

PowerShell 例:

```powershell
cd C:\Users\ryo-n\Codex_dev\memx-resolver\docs\memx_spec_v3\go
go run ./cmd/mem api serve --addr 127.0.0.1:7766 --short "C:\path\to\room\memx\short.db" --journal "C:\path\to\room\memx\journal.db" --knowledge "C:\path\to\room\memx\knowledge.db" --archive "C:\path\to\room\memx\archive.db"
```

**注意**: DB パスは room ごとに分離する。複数 room を扱う場合は、room ごとに異なる DB パスを指定するか、API インスタンスを分ける。

### 3.2 Open-Ark 側設定

`app/config.json` に memx 設定を追加:

```json
{
  "memx_settings": {
    "use_memx": true,
    "memx_api_addr": "http://127.0.0.1:7766",
    "memx_db_path_template": "{room_dir}/memx",
    "memx_request_timeout_sec": 10,
    "gc_execute_enabled": false,
    "migrate_preserve_source": true,
    "phase3_settings": {
      "advanced_resolver_enabled": false,
      "deprecation": {}
    }
  }
}
```

設定値の説明:

| 設定 | 説明 | 既定値 |
|---|---|---|
| `use_memx` | memx 使用有無 | `false` |
| `memx_api_addr` | API アドレス | `http://127.0.0.1:7766` |
| `memx_db_path_template` | DB パステンプレート | `{room_dir}/memx` |
| `gc_execute_enabled` | GC execute 有効化 | `false` |
| `migrate_preserve_source` | 移行時ソース保持 | `true` |
| `advanced_resolver_enabled` | 高度 resolver 有効化 | `false` |

### 3.3 API ヘルスチェック

```powershell
$body = @{ query = "test"; top_k = 1 } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:7766/v1/notes:search `
  -ContentType "application/json" `
  -Body $body
```

期待: `{"notes":[]}` または結果が返る

### 3.4 Open-Ark 起動確認

```powershell
cd C:\Users\ryo-n\Codex_dev\Open-Ark\app
.\.venv\Scripts\python.exe main.py
```

ログで以下を確認:
- `Using MemxAdapter for room: <room_name>` - memx 使用中
- `Using LocalAdapter for room: <room_name>` - フォールバック動作

---

## 4. Phase 別機能

### 4.1 Phase 1: 基本導線

| 機能 | ツール | 説明 |
|---|---|---|
| 保存 | `memx_ingest` | short/journal/knowledge へ保存 |
| 検索 | `memx_search` | 全ストア検索 |
| 参照 | `memx_show` | ID 指定で取得 |

### 4.2 Phase 2: 拡張導線

| 機能 | ツール | 説明 |
|---|---|---|
| コンテキスト検索 | `memx_recall` | recent/relevant/related モード |
| ライフサイクル操作 | `memx_resolve` | promote/archive/link/summarize |
| ガベージコレクション | `memx_gc` | dry-run / execute |
| データ移行 | `memx_migrate` | preview / migrate |

### 4.3 Phase 3: 縮退・移行判断

| 機能 | 説明 |
|---|---|
| 縮退制御 | 旧実装の active/deprecated/read_only/disabled 制御 |
| 移行判断 | 移行可/暫定並行運用/移行不可 の判定 |
| 高度 resolver | 実験的機能（明示的有効化時のみ） |

---

## 5. 検収手順

### 5.1 テスト実行環境

```powershell
cd C:\Users\ryo-n\Codex_dev\Open-Ark\app
.\.venv\Scripts\python.exe -m pytest tests/test_memx_phase2.py tests/test_memx_phase3.py -v
```

### 5.2 現在の検収レイヤー

現在の検収は、次の 2 レイヤーで運用する。

- `core` 検知: `llm_mock` を使わず、削除後のコア導線と Phase 2/3 の基本導線を確認する
- `full` 検知: `llm_mock` を含め、legacy / Phase 2 / Phase 3 の整理済みテスト一式を確認する

### 5.3 Core 検知（`llm_mock` なし）

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/test_legacy_contracts.py `
  tests/test_legacy_equivalence.py `
  tests/test_legacy_disabled_mode.py `
  tests/test_legacy_deletion_simulation.py `
  tests/test_legacy_deletion_candidates.py `
  tests/test_memx_phase2.py `
  tests/test_memx_phase3.py `
  -v -m "not llm_mock"
```

**期待結果**:
- `84 passed, 11 skipped, 84 deselected`

### 5.4 Full 検知（`llm_mock` あり）

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/test_legacy_contracts.py `
  tests/test_legacy_equivalence.py `
  tests/test_legacy_disabled_mode.py `
  tests/test_legacy_deletion_simulation.py `
  tests/test_legacy_deletion_candidates.py `
  tests/test_memx_phase2.py `
  tests/test_memx_phase3.py `
  -v
```

**期待結果**:
- `156 passed, 23 skipped`

### 5.5 Real API 確認

1. memx-resolver を起動
2. Phase 2 / Phase 3 の Real API テストを実行

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/test_memx_phase2.py::TestPhase2RealAPI `
  tests/test_memx_phase3.py::TestPhase3RealAPI `
  -v
```

**期待結果**:
- Real API 到達時に skip ではなく pass すること
### 5.6 個別テスト実行

```powershell
# Phase 2 のみ
.\.venv\Scripts\python.exe -m pytest tests/test_memx_phase2.py -v

# Phase 3 のみ
.\.venv\Scripts\python.exe -m pytest tests/test_memx_phase3.py -v

# Real API テストのみ（API 起動時）
.\.venv\Scripts\python.exe -m pytest tests/test_memx_phase2.py::TestPhase2RealAPI tests/test_memx_phase3.py::TestPhase3RealAPI -v
```

---

## 6. 障害時の対応

### 6.1 API 接続エラー

**症状**: Open-Ark 起動時に memx に接続できない

**確認**:
```powershell
# プロセス確認
Get-Process | Where-Object { $_.ProcessName -like "*mem*" }

# ポート確認
netstat -ano | Select-String 7766

# 設定確認
echo $env:MEMX_API_ADDR
```

**対処**: 
- API が起動していない場合は起動
- `use_memx=false` に設定して LocalAdapter で継続運用

### 6.2 フォールバック動作

**期待動作**:
- `use_memx=true` でも API 障害時は `LocalAdapter` に切り替わる
- Open-Ark 全体は継続動作する

**ログ例**:
```
[MemoryAdapter] WARN: memx unavailable for room: xxx, falling back to LocalAdapter
```

### 6.3 データ整合性

**確認**:
```powershell
# room データ確認
Get-ChildItem "C:\Users\ryo-n\Codex_dev\Open-Ark\app\characters\<room_name>\memory\entities"

# memx DB 確認
Get-ChildItem "C:\Users\ryo-n\Codex_dev\Open-Ark\app\characters\<room_name>\memx"
```

---

## 7. 旧実装の扱い

### 7.1 縮退対象

現在、旧実装の縮退対象は残っていない。削除済みコンポーネントは `DELETED_COMPONENTS` で履歴管理される。

| コンポーネント | 状態 | 代替経路 |
|---|---|---|
| `entity_memory_manager` | deleted | `entity_tools` / `memx_ingest(store="knowledge")` |
| `episodic_memory_manager` | deleted | `memx_ingest(store="journal")` / `memx_recall` |
| `rag_manager` | deleted | `memx_search` / `memx_recall` |
| `dreaming_manager_sync` | deleted | 同期なし運用 |
| `motivation_manager_sync` | deleted | 同期なし運用 |

### 7.2 存続対象（縮退しない）

| コンポーネント | 理由 |
|---|---|
| `memory_manager` | LocalAdapter 動作に必要 |
| `entity_tools` | memx 無効時の代替導線 |
| `memory_tools` | 後方互換性維持 |
| `local_adapter` | フォールバック先として必須 |

### 7.3 ステータス変更

```python
from tools.memx_phase3 import DELETED_COMPONENTS

print(DELETED_COMPONENTS.keys())
# 削除済みコンポーネントの履歴を確認
```

---

## 8. ロールバック手順

### 8.1 設定による復帰

1. `config.json` の `use_memx` を `false` に設定
2. Open-Ark を再起動
3. `LocalAdapter` が使用されることを確認

### 8.2 プログラムによる復帰

```python
from tools.memx_phase3 import execute_rollback

result = execute_rollback("room_name")
# use_memx=false に設定され、LocalAdapter に復帰
```

### 8.3 データ保全

- ローカルデータは削除されない
- memx データも保持可能（`preserve_memx_data=true`）

---

## 9. CI / 継続検証方針

### 9.1 常時実行（Core 検知）

```yaml
# pytest 実行
pytest tests/test_legacy_contracts.py tests/test_legacy_equivalence.py tests/test_legacy_disabled_mode.py tests/test_legacy_deletion_simulation.py tests/test_legacy_deletion_candidates.py tests/test_memx_phase2.py tests/test_memx_phase3.py -v -m "not llm_mock"
```

- Core 検知: 削除後の正常系、LocalAdapter、Phase 2/3 基本導線
- 実依存を隠す重いモックなしで成立する範囲を常時監視

### 9.2 拡張実行（Full 検知）

```yaml
# pytest 実行
pytest tests/test_legacy_contracts.py tests/test_legacy_equivalence.py tests/test_legacy_disabled_mode.py tests/test_legacy_deletion_simulation.py tests/test_legacy_deletion_candidates.py tests/test_memx_phase2.py tests/test_memx_phase3.py -v
```

- `llm_mock` を含む整理済みテスト一式
- UI/LLM 周辺のモック前提テストも含めた回帰確認

### 9.3 手動実行（Real API）

```yaml
# memx-resolver 起動後
pytest tests/test_memx_phase2.py::TestPhase2RealAPI tests/test_memx_phase3.py::TestPhase3RealAPI -v
```

- Real API テスト: recall, resolve, GC の実 API 検証

### 9.4 推奨 CI 構成

| カテゴリ | 実行タイミング | テスト範囲 |
|---|---|---|
| Core 検知 | PR 作成時 | `84 passed, 11 skipped, 84 deselected` |
| Full 検知 | main マージ前後 | `156 passed, 23 skipped` |
| Real API | 手動または専用環境 | Real API テストが skip ではなく pass |

---

## 10. 移行判断

### 10.1 判断基準

```python
from tools.memx_phase3 import judge_migration_status

judgment = judge_migration_status("room_name")
print(judgment.verdict)  # 移行可 / 暫定並行運用 / 移行不可
```

### 10.2 判定ロジック

| 判定 | 条件 |
|---|---|
| 移行可 | 全検証項目合格、MemxAdapter 到達確認 OK |
| 暫定並行運用 | 一部検証項目不合格、または API 到達性不安定 |
| 移行不可 | 検証項目の多くが不合格、LocalAdapter 運用推奨 |

---

## 11. 参照資料

- `docs/MEMX_INTEGRATION_REQUIREMENTS.md` - 要件定義
- `docs/MEMX_PHASE2_SPECIFICATION.md` - Phase 2 仕様
- `app/tools/memx_phase3.py` - Phase 3 機能モジュール
- `app/tests/test_memx_phase2.py` - Phase 2 テスト
- `app/tests/test_memx_phase3.py` - Phase 3 テスト

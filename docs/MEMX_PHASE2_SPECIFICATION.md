# memx-resolver Phase 2 仕様書

## 1. 文書の位置づけ

本書は Phase 2 実装前チェックリスト（10項目）を確定させ、Phase 2 の実装内容、テスト観点、完了条件を定義する。

Phase 2 は Phase 1 の完了を前提とし、検索導線拡張、resolver連携、GC機能、移行補助を段階的に導入する。

---

## 2. Phase 2 実装前チェックリスト確定

### 2.1 API契約確定 [No.1]

#### 2.1.1 memx_recall API契約

**Request:**
```json
{
  "query": "string",
  "room_name": "string",
  "context": {
    "current_topic": "string?",
    "time_range": {
      "start": "ISO8601?",
      "end": "ISO8601?"
    }
  },
  "recall_mode": "recent | relevant | related",
  "top_k": 5
}
```

**Response:**
```json
{
  "results": [
    {
      "note_id": "string",
      "title": "string",
      "summary": "string",
      "store": "short | journal | knowledge | archive",
      "relevance_score": 0.0-1.0,
      "timestamp": "ISO8601"
    }
  ],
  "total_count": 10,
  "recall_source": "memx | local",
  "mode_used": "string"
}
```

**Errors:**
| Code | Message | Condition |
|---|---|---|
| RECALL_ERROR | "Recall query failed" | memx API search failure |
| INVALID_MODE | "Invalid recall_mode" | recall_mode not in enum |

#### 2.1.2 docs:resolve API契約

**Request:**
```json
{
  "note_id": "string",
  "store": "short | journal | knowledge",
  "resolve_action": "promote | archive | link | summarize",
  "target_store": "knowledge | archive?",
  "metadata": {
    "entity_name": "string?",
    "confidence": 0.0-1.0?
  }
}
```

**Response:**
```json
{
  "resolved_note": {
    "id": "string",
    "original_id": "string",
    "store": "string",
    "status": "resolved"
  },
  "action_taken": "string",
  "linked_entities": ["string"]
}
```

**Errors:**
| Code | Message | Condition |
|---|---|---|
| NOT_FOUND | "Note not found" | note_id invalid |
| RESOLVE_FAILED | "Resolve action failed" | promote/archive/link failure |
| INVALID_ACTION | "Invalid resolve_action" | action not in enum |

#### 2.1.3 GC API契約

**Request:**
```json
{
  "mode": "dry-run | execute",
  "room_name": "string",
  "gc_scope": {
    "stores": ["short", "journal"],
    "criteria": {
      "age_days_min": 30,
      "access_count_max": 0,
      "exclude_tags": ["important", "persistent"]
    }
  }
}
```

**Response (dry-run):**
```json
{
  "mode": "dry-run",
  "candidates": [
    {
      "note_id": "string",
      "title": "string",
      "store": "string",
      "reason": "age | low_access | obsolete",
      "age_days": 45,
      "access_count": 0
    }
  ],
  "total_candidates": 5,
  "would_delete": 5,
  "safety_checks_passed": true
}
```

**Response (execute):**
```json
{
  "mode": "execute",
  "deleted_count": 5,
  "deleted_ids": ["string"],
  "archived_ids": ["string"],
  "errors": [
    {
      "note_id": "string",
      "error": "string"
    }
  ],
  "timestamp": "ISO8601"
}
```

**Errors:**
| Code | Message | Condition |
|---|---|---|
| GC_FORBIDDEN | "GC execute forbidden by policy" | safety check failed |
| GC_ERROR | "GC execution failed" | unexpected error during GC |
| INVALID_MODE | "Invalid GC mode" | mode not dry-run/execute |

#### 2.1.4 移行補助 API契約

**Request:**
```json
{
  "source": "entity_memory | episode | question | insight",
  "room_name": "string",
  "target_store": "knowledge | journal | short",
  "mode": "preview | migrate",
  "filters": {
    "entity_names": ["string?"],
    "min_importance": 0.0?
  }
}
```

**Response (preview):**
```json
{
  "mode": "preview",
  "candidates": [
    {
      "source_type": "string",
      "source_id": "string",
      "source_name": "string",
      "content_preview": "string (200 chars)",
      "target_store": "string",
      "mapped_fields": {
        "title": "string",
        "body": "string",
        "tags": ["string"]
      }
    }
  ],
  "total_candidates": 10,
  "would_create": 10
}
```

**Response (migrate):**
```json
{
  "mode": "migrate",
  "created_notes": [
    {
      "note_id": "string",
      "source_id": "string",
      "source_type": "string"
    }
  ],
  "errors": [
    {
      "source_id": "string",
      "error": "string"
    }
  ],
  "source_files_preserved": true,
  "timestamp": "ISO8601"
}
```

---

### 2.2 resolver系対象範囲確定 [No.2]

| resolver機能 | 呼び出し元 | 対象ストア | 制限 |
|---|---|---|---|
| promote | memx_resolve tool | short→knowledge | エンティティ名必須 |
| archive | memx_resolve tool | journal→archive | 重要タグ除外 |
| link | memx_resolve tool | knowledge内 | 既存エンティティ間のみ |
| summarize | memx_resolve tool | journal内 | 重複ログのみ |

**呼び出し元制限:**
- `memx_resolve` tool からの呼び出しのみ
- `DreamingManager`, `MotivationManager` からは直接呼び出さない
- `entity_tools` からは promote のみ呼び出し可能（明示的フラグ）

---

### 2.3 GC実行モード定義 [No.3]

#### 2.3.1 dry-run モード

| 特性 | 定義 |
|---|---|---|
| 動作 | 削除候補をリストアップのみ、実削除なし |
| 出力 | 削除対象ID、理由、年齢、アクセス回数 |
| 副作用 | なし（観測のみ） |
| 必要権限 | なし（誰でも実行可能） |
| ログレベル | INFO |

#### 2.3.2 execute モード

| 特性 | 定義 |
|---|---|---|
| 動作 | 削除候補を実際に削除またはarchiveへ移動 |
| 出力 | 削除数、削除ID、archive移動ID、エラー |
| 副作用 | あり（データ削除） |
| 必要権限 | `gc_execute_enabled=true` 設定 + 明示的確認 |
| ログレベル | WARN + 詳細記録 |
| 事前条件 | dry-run 実行 + safety_checks_passed=true |

---

### 2.4 GC禁止事項明文化 [No.4]

| 禁止事項 | 理由 | 検証方法 |
|---|---|---|
| entity_memory ファイル削除禁止 | 既存知識資産保護 | source != "entity_memory" |
| important タグ付き削除禁止 | 重要記憶保護 | exclude_tags contains "important" |
| knowledge ストアからの削除禁止 | 確定事実は永続 | gc_scope.stores excludes "knowledge" |
| room 間境界を越える削除禁止 | room分離維持 | room_name 一致確認 |
| アクセス回数 > 0 の削除禁止 | 使用中記憶保護 | access_count_max = 0 |
| 作成日 < 7日 の削除禁止 | 新規記憶保護 | age_days_min >= 7 |

**違反時の動作:**
- execute モード: `GC_FORBIDDEN` エラー + 実行拒否
- dry-run モード: 該当候補を "protected" マーク + 削除対象除外

---

### 2.5 既存機構との責務分界 [No.5]

| 情報タイプ | 保存先 | 読み取り元 | 重複時優先 |
|---|---|---|---|
| エンティティ知識 | knowledge (memx) + entity_memory (local) | memx優先、local補完 | memx |
| エピソード記憶 | journal (memx) + episodes.json (local) | memx優先 | memx |
| 未解決の問い | short (memx) + open_questions.json (local) | memx優先 | memx |
| 洞察・夢 | journal (memx) | memxのみ | memx |
| 一時メモ | short (memx) | memxのみ | memx |

**Phase 2 保存導線:**
- `DreamingManager`: insight → `sync_insight_to_memx()` → journal
- `MotivationManager`: question → `sync_question_to_memx()` → short
- `entity_tools`: entity update → `sync_entity_to_memx()` → knowledge
- `episodic_memory_manager`: episode → `sync_episode_to_memx()` → journal

**読み取り導線:**
- `memx_search` tool: 全ストア検索
- `memx_recall` tool: コンテキスト付き検索
- `memx_show` tool: ID指定取得

---

### 2.6 移行対象/非対象明確化 [No.6]

#### 2.6.1 移行対象

| ソース | 対象ストア | 条件 |
|---|---|---|
| entity_memory/*.md | knowledge | 全エンティティ |
| episodes.json | journal | importance >= 0.5 |
| open_questions.json | short | status == "open" |

#### 2.6.2 移行非対象

| ソース | 理由 |
|---|---|---|
| rag_index | Phase 3 で検討 |
| dreams_archive | journal内で管理、別移行不要 |
| temporary_notes | 意味なし、Phase 2移行対象外 |
| private/config.json | 移行対象外（設定ファイル） |

#### 2.6.3 移行後のソースファイル処理

| モード | 動作 |
|---|---|---|
| preview | ソースファイル維持 |
| migrate | ソースファイル維持（削除しない） |
| migrate_with_cleanup | ソースファイルを ".migrated" マーク（削除はPhase 3） |

---

### 2.7 ロールバック方針 [No.7]

| 操作 | ロールバック方法 |
|---|---|---|
| memx_resolve | 元note_idから復元（store変更前データは残存） |
| GC execute | archive移動分は復元可能、削除分は不可 |
| migrate | ソースファイル維持により復元可能 |
| 全体 | `use_memx=false` で旧導線へ復帰 |

**ロールバック実行条件:**
- migrate後24時間以内
- GC execute後、archive移動分のみ（削除分は不可）

---

### 2.8 観測ログ項目 [No.8]

| 操作 | ログ項目 |
|---|---|---|
| memx_recall | query, room_name, mode, results_count, source |
| memx_resolve | note_id, action, result, linked_entities |
| GC dry-run | candidates_count, safety_checks_passed |
| GC execute | deleted_count, archived_count, errors |
| migrate | source_type, created_count, errors |

**ログレベル:**
- INFO: 正常操作
- WARN: GC execute, migrate, resolve 変更操作
- ERROR: 操作失敗

---

### 2.9 実API統合確認最小セット [No.9]

| テスト | 内容 | API必要 |
|---|---|---|
| resolver呼び出し | docs:resolve 実API呼び出し | Yes |
| GC dry-run | 実APIで候補リスト取得 | Yes |
| GC execute | 実APIで削除実行（テストDB） | Yes |
| fallback維持 | Phase 1 fallback動作確認 | No（モック可） |

---

### 2.10 Phase 2完了/不合格条件 [No.10]

#### 2.10.1 完了条件

| ID | 条件 |
|---|---|
| AC-P2-001 | `memx_recall` が memx API 正常時に結果を返せる |
| AC-P2-002 | `memx_resolve` promote が short→knowledge 昇格できる |
| AC-P2-003 | `memx_resolve` archive が journal→archive 移動できる |
| AC-P2-004 | GC dry-run が削除候補をリストアップできる |
| AC-P2-005 | GC execute が safety_checks なしでは実行拒否される |
| AC-P2-006 | GC execute が important タグ付きを削除対象外とする |
| AC-P2-007 | 移行 preview が entity_memory から knowledge へ候補表示できる |
| AC-P2-008 | 移行 migrate がソースファイルを削除しない |
| AC-P2-009 | use_memx=true で memx API 停止時も fallback 維持 |
| AC-P2-010 | ログ出力が Phase 2 操作を追跡可能 |

#### 2.10.2 不合格条件

| 条件 |
|---|
| GC execute が important タグ付きを削除する |
| 移行 migrate がソースファイルを削除する |
| knowledge ストアから GC 削除が発生する |
| room 間で GC 削除が混線する |
| resolver が DreamingManager から直接呼び出される |

---

## 3. Phase 2 実装項目

### 3.1 新ツール

| ツール名 | 機能 |
|---|---|---|
| memx_recall | コンテキスト付き検索（recent/relevant/related モード） |
| memx_resolve | note 解決（promote/archive/link/summarize） |
| memx_gc | GC 実行（dry-run/execute） |
| memx_migrate | 移行補助（preview/migrate） |

### 3.2 新APIクライアントメソッド

| メソッド | 機能 |
|---|---|---|
| recall() | recall_mode 付き検索 |
| resolve() | resolve_action 実行 |
| gc() | GC dry-run/execute |
| migrate() | 移行 preview/migrate |

### 3.3 新Adapterメソッド

| メソッド | 機能 |
|---|---|---|
| recall() | Adapter経由recall |
| resolve() | Adapter経由resolve |
| gc() | Adapter経由GC |

### 3.4 設定追加

```json
"memx_settings": {
  "use_memx": true,
  "memx_api_addr": "http://127.0.0.1:7766",
  "memx_db_path_template": "{room_dir}/memx",
  "memx_request_timeout_sec": 10,
  "gc_execute_enabled": false,
  "gc_default_criteria": {
    "age_days_min": 30,
    "access_count_max": 0,
    "exclude_tags": ["important", "persistent"]
  },
  "migrate_preserve_source": true
}
```

---

## 4. Phase 2 実装順序

| Step | 内容 | 前提 |
|---|---|---|
| 1 | memx_client 拡張（recall/resolve/gc/migrate） | Phase 1 |
| 2 | memx_adapter 拡張 | Step 1 |
| 3 | memx_recall tool 実装 | Step 2 |
| 4 | memx_resolve tool 実装 | Step 2 |
| 5 | memx_gc tool 実装 | Step 2 |
| 6 | memx_migrate helper 実装 | Step 2 |
| 7 | 設定追加 | Step 6 |
| 8 | テスト実装 | Step 7 |
| 9 | 統合確認 | Step 8 |

---

## 5. 参照資料

- `MEMX_INTEGRATION_REQUIREMENTS.md`
- `docs/MEMX_SURVEY_RESULTS.md`
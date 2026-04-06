# memx-resolver Phase 2 テスト設計書

## 1. 文書の位置づけ

本書は Phase 2 仕様書に基づき、テストケース、テスト観点、テスト実行順序を定義する。

---

## 2. テスト分類

### 2.1 モックテスト（APIなしで実行可能）

| テストID | 内容 | 目的 |
|---|---|---|---|
| T-MOCK-001 | memx_recall 基本レスポンス解析 | API契約確認 |
| T-MOCK-002 | memx_resolve promote 成功 | promote動作確認 |
| T-MOCK-003 | memx_resolve archive 成功 | archive動作確認 |
| T-MOCK-004 | GC dry-run 基本動作 | 削除候補リスト確認 |
| T-MOCK-005 | GC execute 拒否（safety_check失敗） | 禁止事項確認 |
| T-MOCK-006 | GC important タグ除外 | 禁止事項確認 |
| T-MOCK-007 | migrate preview 基本動作 | 移行候補確認 |
| T-MOCK-008 | migrate ソースファイル維持 | 非削除確認 |
| T-MOCK-009 | fallback維持確認 | Phase 1継続確認 |

### 2.2 実APIテスト（memx-resolver起動必要）

| テストID | 内容 | 前提 |
|---|---|---|
| T-API-001 | memx_recall 実API呼び出し | memx-resolver起動 |
| T-API-002 | memx_resolve promote 実API | memx-resolver起動 + テストnote |
| T-API-003 | GC dry-run 実API | memx-resolver起動 + テストDB |
| T-API-004 | GC execute 実API | memx-resolver起動 + テストDB |

---

## 3. テストケース詳細

### 3.1 memx_recall テスト

#### T-MOCK-001: memx_recall 基本レスポンス解析

**前提:** モックMemxClient

**入力:**
```python
query = "テストクエリ"
room_name = "test_room"
recall_mode = "relevant"
top_k = 5
```

**期待結果:**
- results リスト取得
- relevance_score が 0.0-1.0 範囲
- recall_source が "memx"
- total_count >= 0

**不合格条件:**
- relevance_score が範囲外
- recall_source が不正

#### T-API-001: memx_recall 実API呼び出し

**前提:** memx-resolver起動, テストnote存在

**入力:**
```python
query = "実際の検索ワード"
room_name = "api_test_room"
recall_mode = "recent"
top_k = 3
```

**期待結果:**
- 実APIからresults取得
- results[0].note_id が有効
- results[0].timestamp が ISO8601

---

### 3.2 memx_resolve テスト

#### T-MOCK-002: memx_resolve promote 成功

**前提:** モックMemxClient, short note存在

**入力:**
```python
note_id = "short-001"
store = "short"
resolve_action = "promote"
target_store = "knowledge"
metadata = {"entity_name": "テストエンティティ"}
```

**期待結果:**
- resolved_note.id が新ID
- resolved_note.store == "knowledge"
- resolved_note.status == "resolved"
- action_taken == "promote"

#### T-MOCK-003: memx_resolve archive 成功

**前提:** モックMemxClient, journal note存在

**入力:**
```python
note_id = "journal-001"
store = "journal"
resolve_action = "archive"
```

**期待結果:**
- resolved_note.store == "archive"
- action_taken == "archive"

#### T-API-002: memx_resolve promote 実API

**前提:** memx-resolver起動, short note作成済み

**入力:**
```python
note_id = "created_short_id"
store = "short"
resolve_action = "promote"
target_store = "knowledge"
```

**期待結果:**
- 実APIで knowledge ストアにnote作成
- 元short noteがresolved状態

---

### 3.3 GC テスト

#### T-MOCK-004: GC dry-run 基本動作

**前提:** モックMemxClient, テストDB

**入力:**
```python
mode = "dry-run"
room_name = "gc_test_room"
gc_scope = {
    "stores": ["short", "journal"],
    "criteria": {
        "age_days_min": 30,
        "access_count_max": 0
    }
}
```

**期待結果:**
- candidates リスト取得
- each candidate.reason が有効
- safety_checks_passed == True
- mode == "dry-run"

#### T-MOCK-005: GC execute 拒否（safety_check失敗）

**前提:** モックMemxClient, safety_checks_passed=False

**入力:**
```python
mode = "execute"
gc_scope = {"stores": ["knowledge"]}  # 禁止ストア
```

**期待結果:**
- GC_FORBIDDEN エラー
- 削除実行なし
- エラーメッセージ含む

**不合格条件:**
- execute 実行された
- knowledge ストア削除発生

#### T-MOCK-006: GC important タグ除外

**前提:** モックMemxClient, importantタグ付きnote

**入力:**
```python
mode = "dry-run"
gc_scope = {
    "criteria": {
        "exclude_tags": ["important"]
    }
}
```

**期待結果:**
- importantタグ付きがcandidates除外
- candidatesに "important" 含まない
- would_deleteがimportant除外数

**不合格条件:**
- importantタグ付きが削除対象

#### T-API-003: GC dry-run 実API

**前提:** memx-resolver起動, テストDBに古いnote

**入力:**
```python
mode = "dry-run"
gc_scope = {"stores": ["short"]}
```

**期待結果:**
- 実APIからcandidates取得
- candidates各項目が有効値

#### T-API-004: GC execute 実API

**前提:** memx-resolver起動, テストDB, gc_execute_enabled=True

**入力:**
```python
mode = "execute"
gc_scope = {
    "stores": ["short"],
    "criteria": {"age_days_min": 90}
}
```

**期待結果:**
- deleted_count > 0
- deleted_ids リスト取得
- errors リスト空または有効

---

### 3.4 migrate テスト

#### T-MOCK-007: migrate preview 基本動作

**前提:** モック, entity_memory存在

**入力:**
```python
source = "entity_memory"
room_name = "migrate_test_room"
target_store = "knowledge"
mode = "preview"
```

**期待結果:**
- candidates リスト取得
- each candidate.source_type == "entity_memory"
- each candidate.target_store == "knowledge"
- mapped_fields 有効

#### T-MOCK-008: migrate ソースファイル維持

**前提:** モック, entity_memoryファイル存在

**入力:**
```python
source = "entity_memory"
mode = "migrate"
```

**期待結果:**
- source_files_preserved == True
- 元entity_memoryファイル存在維持

**不合格条件:**
- ソースファイル削除

---

### 3.5 fallback テスト

#### T-MOCK-009: fallback維持確認

**前提:** use_memx=true, API停止モック

**入力:**
```python
use_memx = True
api_unavailable = True
```

**期待結果:**
- LocalAdapter フォールバック
- 主要操作継続可能
- ログにフォールバック記録

---

## 4. Phase 2 受け入れテスト

### 4.1 AC-P2-001〜AC-P2-010 テスト対応

| AC | テストID | テスト方法 |
|---|---|---|
| AC-P2-001 | T-API-001 | 実API |
| AC-P2-002 | T-API-002 | 実API |
| AC-P2-003 | T-MOCK-003 | モック |
| AC-P2-004 | T-API-003 | 実API |
| AC-P2-005 | T-MOCK-005 | モック |
| AC-P2-006 | T-MOCK-006 | モック |
| AC-P2-007 | T-MOCK-007 | モック |
| AC-P2-008 | T-MOCK-008 | モック |
| AC-P2-009 | T-MOCK-009 | モック |
| AC-P2-010 | ログ出力テスト | モック |

### 4.2 不合格条件テスト

| 不合格条件 | テストID | 検証方法 |
|---|---|---|
| importantタグ削除 | T-MOCK-006 | GC execute重要タグ除外確認 |
| ソースファイル削除 | T-MOCK-008 | migrate後ファイル存在確認 |
| knowledgeストアGC削除 | T-MOCK-005 | GC execute禁止確認 |
| room間GC混線 | T-ROOM-001 | room境界確認テスト |
| DreamingManager直接呼び出し | T-ARCH-001 | 呼び出し経路確認 |

---

## 5. テスト実装構成

### 5.1 テストファイル

```
tests/test_memx_phase2.py
├── TestMemxRecall
│   ├── test_recall_mock_basic (T-MOCK-001)
│   └── test_recall_api (T-API-001) - skip if no API
├── TestMemxResolve
│   ├── test_resolve_promote_mock (T-MOCK-002)
│   ├── test_resolve_archive_mock (T-MOCK-003)
│   └── test_resolve_promote_api (T-API-002) - skip if no API
├── TestMemxGC
│   ├── test_gc_dryrun_mock (T-MOCK-004)
│   ├── test_gc_execute_forbidden (T-MOCK-005)
│   ├── test_gc_important_protected (T-MOCK-006)
│   ├── test_gc_dryrun_api (T-API-003) - skip if no API
│   └── test_gc_execute_api (T-API-004) - skip if no API
├── TestMemxMigrate
│   ├── test_migrate_preview_mock (T-MOCK-007)
│   └── test_migrate_source_preserved (T-MOCK-008)
├── TestPhase2Acceptance
│   ├── test_ac_p2_001_thru_010
│   └── test_phase2_rejection_conditions
└── TestPhase2Logging
    ├── test_recall_logging
    ├── test_resolve_logging
    ├── test_gc_logging
    └── test_migrate_logging
```

### 5.2 テスト実行順序

1. モックテスト実行（APIなし）
2. API起動確認
3. 実APIテスト実行（条件付き）
4. 受け入れテスト実行
5. ログテスト実行

---

## 6. テスト用モックデータ

### 6.1 recall モックデータ

```python
MOCK_RECALL_RESPONSE = {
    "results": [
        {
            "note_id": "recall-001",
            "title": "テスト結果1",
            "summary": "要約",
            "store": "journal",
            "relevance_score": 0.85,
            "timestamp": "2024-01-01T00:00:00"
        }
    ],
    "total_count": 1,
    "recall_source": "memx",
    "mode_used": "relevant"
}
```

### 6.2 resolve モックデータ

```python
MOCK_PROMOTE_RESPONSE = {
    "resolved_note": {
        "id": "knowledge-001",
        "original_id": "short-001",
        "store": "knowledge",
        "status": "resolved"
    },
    "action_taken": "promote",
    "linked_entities": ["テストエンティティ"]
}

MOCK_ARCHIVE_RESPONSE = {
    "resolved_note": {
        "id": "archive-001",
        "original_id": "journal-001",
        "store": "archive",
        "status": "resolved"
    },
    "action_taken": "archive",
    "linked_entities": []
}
```

### 6.3 GC モックデータ

```python
MOCK_GC_DRYRUN_RESPONSE = {
    "mode": "dry-run",
    "candidates": [
        {
            "note_id": "gc-001",
            "title": "古いメモ",
            "store": "short",
            "reason": "age",
            "age_days": 45,
            "access_count": 0
        }
    ],
    "total_candidates": 1,
    "would_delete": 1,
    "safety_checks_passed": True
}

MOCK_GC_EXECUTE_RESPONSE = {
    "mode": "execute",
    "deleted_count": 1,
    "deleted_ids": ["gc-001"],
    "archived_ids": [],
    "errors": [],
    "timestamp": "2024-01-01T00:00:00"
}
```

### 6.4 migrate モックデータ

```python
MOCK_MIGRATE_PREVIEW_RESPONSE = {
    "mode": "preview",
    "candidates": [
        {
            "source_type": "entity_memory",
            "source_id": "entity-001",
            "source_name": "テスト人物",
            "content_preview": "# テスト人物\n...",
            "target_store": "knowledge",
            "mapped_fields": {
                "title": "テスト人物",
                "body": "...",
                "tags": ["entity"]
            }
        }
    ],
    "total_candidates": 1,
    "would_create": 1
}

MOCK_MIGRATE_RESPONSE = {
    "mode": "migrate",
    "created_notes": [
        {
            "note_id": "knowledge-001",
            "source_id": "entity-001",
            "source_type": "entity_memory"
        }
    ],
    "errors": [],
    "source_files_preserved": True,
    "timestamp": "2024-01-01T00:00:00"
}
```

---

## 7. 参照資料

- `MEMX_PHASE2_SPECIFICATION.md`
- `MEMX_INTEGRATION_REQUIREMENTS.md`
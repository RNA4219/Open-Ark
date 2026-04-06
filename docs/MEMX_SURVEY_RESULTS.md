# memx-resolver 統合 調査結果メモ

## 1. この文書の位置づけ

本書は、要件書とロードマップを補助するための調査メモである。  
設計判断そのものは `MEMX_INTEGRATION_REQUIREMENTS.md` を正とし、本書は「何が分かっていて、何が未確認か」を整理する用途で使う。

---

## 2. Open-Ark 側の観察結果

### 2.1 影響が大きい主要ファイル

| ファイル | 役割 | memx 統合での論点 |
|---|---|---|
| `app/entity_memory_manager.py` | エンティティ記憶 | `knowledge` との接続点候補 |
| `app/episodic_memory_manager.py` | エピソード記憶 | `journal` との接続点候補 |
| `app/rag_manager.py` | 記憶検索 | 既存検索導線との住み分けが必要 |
| `app/dreaming_manager.py` | 洞察・夢・睡眠時処理 | `journal` への保存導線候補 |
| `app/motivation_manager.py` | 好奇心、問い、内部状態 | `short` への保存導線候補 |
| `app/tools/entity_tools.py` | entity 系ツール | adapter 化の初期対象 |
| `app/tools/memory_tools.py` | recall 系ツール | 検索導線の差し替え候補 |
| `app/ui_handlers.py` | UI 層 | adapter の選択点を増やし過ぎない工夫が必要 |
| `app/agent/graph.py` | ツール登録・全体配線 | 新ツール追加時の主要変更点 |

### 2.2 初期導入で意識すべき点

- 現状の記憶機構は `manager` と `tool` に分散している
- いきなり既存マネージャを削除すると影響範囲が広い
- 先に adapter を入れて接続点を統一する方が安全

### 2.3 削除についての結論

現時点では「削除対象の候補」は挙げられるが、削除の即時実行は不可。  
理由:

- 既存ツールと UI からの参照が多い
- 検索品質比較が未完了
- 移行スクリプトとロールバックが未整備

---

## 3. `memx-resolver` API 側の観察結果

### 3.1 Phase 1 で前提にする API

| エンドポイント | 用途 |
|---|---|
| `POST /v1/notes:ingest` | 保存 |
| `POST /v1/notes:search` | 検索 |
| `GET /v1/notes/{id}` | 詳細参照 |

### 3.2 クライアント実装で気をつけること

- request/response 契約は実コードまたは OpenAPI で最終確認する
- `db_path` の扱いは API 契約依存なので、実装前に固定する
- タイムアウト、接続拒否、HTTP エラーを分けて扱う

### 3.3 現時点で未確認の論点

- `db_path` を毎リクエストで渡すのか、サーバー起動時に固定するのか
- search レスポンスに含まれるメタデータの確定形
- `summary` や `tags` の扱いの必須/任意

---

## 4. Open-Ark 側で先に決めるべきこと

### 4.1 設定

最低限必要な設定候補:

- `use_memx`
- `memx_api_addr`
- `memx_db_path_template`
- `memx_request_timeout_sec`
- `auto_start_memx` は任意

### 4.2 adapter の責務分離

| レイヤ | 責務 |
|---|---|
| `memx_client.py` | HTTP 通信のみ |
| `MemxAdapter` | Open-Ark 用の引数整形と API 呼び出し |
| `LocalAdapter` | 既存 manager 群のラップ |
| 呼び出し側 | adapter の選択とフォールバック |

### 4.3 最初の接続対象

優先度順:

1. `memx_tools.py`
2. `entity_tools.py`
3. `memory_tools.py`
4. `dreaming_manager.py`
5. `motivation_manager.py`

---

## 5. OpenClaw について

OpenClaw からも同じ API を利用する構想は自然だが、Open-Ark の初期統合とは分けて扱うべきである。  
この repo の作業としては、次の一文で十分:

- 「OpenClaw は将来の別クライアント候補であり、Open-Ark Phase 1 の完了条件には含めない」

---

## 6. 現時点の推奨アクション

1. `memx-resolver` API 契約の最終確認
2. Open-Ark 側の `memx_client.py` 実装
3. `MemoryAdapter` / `MemxAdapter` / `LocalAdapter` 実装
4. `memx_ingest` / `memx_search` / `memx_show` の追加
5. 既存検索・保存導線との役割分担整理

---

## 7. 関連文書

- `docs/MEMX_INTEGRATION_REQUIREMENTS.md`
- `docs/MEMX_IMPL_ROADMAP.md`
- `docs/MEMX_BIRDEYE.md`
- `docs/MEMX_RUNBOOK.md`
- `docs/AUTO_RESOLVE_AND_CONVERT_IMPL.md`

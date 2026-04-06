# memx-resolver 統合ロードマップ

## 1. このロードマップの扱い

本ロードマップは Open-Ark 側の作業計画である。  
OpenClaw など他 repo の作業は依存先または後続作業として触れるに留め、ここでは Open-Ark で完結する実装順を優先する。

---

## 2. 完了イメージ

Phase 1 完了時点で目指す状態:

- Open-Ark に `MemoryAdapter` 層が入っている
- `use_memx=true` で memx API を利用できる
- API 障害時は `LocalAdapter` へフォールバックできる
- 新規ツール `memx_ingest` / `memx_search` / `memx_show` が使える
- 既存記憶機能はまだ残っている

---

## 3. フェーズ定義

### Phase 1: 接続基盤と Adapter 導入

対象:

- `memx_client.py`
- `adapters/`
- `tools/memx_tools.py`
- 設定追加

完了条件:

- API クライアントが `ingest/search/show` を実行できる
- Adapter を 1 箇所で選べる
- `use_memx=false` で従来動作を維持できる

### Phase 2: 利用導線の拡張

対象:

- `dreaming_manager.py`
- `motivation_manager.py`
- `tools/entity_tools.py`
- `tools/memory_tools.py`

完了条件:

- 新規保存経路の一部が memx を使える
- `memx_recall` 相当の導線を整理できる
- dry-run 付き移行スクリプトの要件が固まる

### Phase 3: 移行と縮退

対象:

- 既存データ移行
- 重複ツール整理
- 旧記憶実装の縮退

完了条件:

- memx が主要導線になる
- 旧実装の削除可否を判断できる

---

## 4. 実装順序

### Step 1: API 契約確認

- [x] `memx-resolver` の `ingest/search/show` request/response を確認
- [x] `db_path` の指定方法を確認（Phase 1ではAPI起動時固定想定）
- [x] タイムアウトとエラー応答の扱いを決める

成果物:

- 実装前提の確定
- クライアント側のデータモデル案

### Step 2: Open-Ark 側クライアント実装

- [x] `app/memx_client.py` を追加
- [x] API アドレス、タイムアウト、`db_path` を引数化
- [x] 接続エラーと API エラーを区別して返す

成果物:

- memx API を叩ける薄い Python クライアント

### Step 3: Adapter 層実装

- [x] `app/adapters/memory_adapter.py`
- [x] `app/adapters/memx_adapter.py`
- [x] `app/adapters/local_adapter.py`
- [x] Adapter ファクトリまたは選択関数

成果物:

- `use_memx` と接続状態に応じて adapter を切り替えられる

### Step 4: 設定追加

- [x] `app/config.json.example` に memx 項目を追加
- [x] 設定読込側のコードパスを整理
- [x] `MEMX_API_ADDR` 上書きを実装

成果物:

- 設定で memx 利用有無を切り替えられる

### Step 5: ツール追加

- [x] `app/tools/memx_tools.py` を追加
- [x] `memx_ingest`
- [x] `memx_search`
- [x] `memx_show`
- [x] `memx_recall`
- [x] `agent/graph.py` でツール登録

成果物:

- AI ツール経由で memx の基本操作が可能

### Step 6: 既存導線との接続

- [ ] `entity_tools.py` との役割分担整理
- [ ] `memory_tools.py` との役割分担整理
- [ ] `dreaming_manager.py` / `motivation_manager.py` で新規保存経路の接続点を決める

成果物:

- 既存機能を壊さず、差し込み可能な接続点ができる

### Step 7: 受け入れ確認

- [ ] `use_memx=false` で従来動作
- [ ] `use_memx=true` かつ API 起動中で memx 利用
- [ ] `use_memx=true` かつ API 停止中で LocalAdapter にフォールバック
- [ ] room ごとに DB パスが分かれる

---

## 5. 変更対象の優先度

### 優先度 A

- `app/config.json.example`
- `app/config_manager.py`
- `app/memx_client.py`
- `app/adapters/*`
- `app/tools/memx_tools.py`

### 優先度 B

- `app/tools/entity_tools.py`
- `app/tools/memory_tools.py`
- `app/dreaming_manager.py`
- `app/motivation_manager.py`

### 優先度 C

- 移行スクリプト
- GC 統合
- 旧機能の縮退

---

## 6. repo 外依存

Open-Ark 実装の前提として確認すべき依存:

- `memx-resolver` の API 契約
- `memx-resolver` 側の `db_path` 運用

後続の別トラック:

- OpenClaw plugin 実装
- 複数クライアント同時接続の検証

---

## 7. 先送りにすること

以下は Phase 1 ではやらない。

- OpenClaw plugin の作成
- 既存ファイルの削除
- 全検索導線の memx 置換
- GC 自動実行
- resolver 高度機能の全面導入

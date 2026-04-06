# memx-resolver 統合 Birdseye

## 1. 要約

Open-Ark への memx 統合は、「既存記憶をすべて置き換える作業」ではなく、まず `MemoryAdapter` を導入して新しい記憶 API を差し込めるようにする作業である。  
初期段階では memx と既存実装を並走させ、接続失敗時も Open-Ark が継続動作できることを重視する。

---

## 2. 全体像

```text
                           +---------------------------+
                           | memx-resolver API         |
                           | - ingest                  |
                           | - search                  |
                           | - show                    |
                           +---------------------------+
                                      ^
                                      | HTTP
                                      |
+---------------------------+         |
| Open-Ark                  |         |
|                           |         |
|  tools/memx_tools.py      |---------+
|           |
|           v
|    MemoryAdapter
|      |        |
|      |        +--------------------+
|      |                             |
|      v                             v
|  MemxAdapter                  LocalAdapter
|                                     |
|                                     +--> entity / episodic / rag / dreaming
+---------------------------+
```

---

## 3. 何が変わるか

### 3.1 新しく入るもの

- `memx_client.py`
- `MemoryAdapter`
- `MemxAdapter`
- `LocalAdapter`
- `memx_ingest`
- `memx_search`
- `memx_show`

### 3.2 すぐには消さないもの

- `entity_memory_manager.py`
- `episodic_memory_manager.py`
- `rag_manager.py`
- 既存の entity / memory 系ツール

理由:

- 検索品質や保存仕様の差がまだある
- 既存 room のデータ互換を壊さないため
- フォールバック経路を確保するため

---

## 4. ストア階層

```text
knowledge
  永続知識、定義、人物・概念の属性

journal
  エピソード、洞察、夢、進捗、意思決定

short
  未解決の問い、作業メモ、一時的関心

archive
  GC 後に退避した古い記憶
```

### 4.1 対応イメージ

| Open-Ark 側の情報 | 主な保存先 |
|---|---|
| エンティティ記憶 | `knowledge` |
| エピソード記憶 | `journal` |
| 夢・洞察 | `journal` |
| 未解決の問い | `short` |

---

## 5. 接続方針

### 5.1 API アドレス

- 既定: `http://127.0.0.1:7766`
- 上書き: `MEMX_API_ADDR`

### 5.2 room 分離

- room ごとの DB は `{room_dir}/memx` を既定とする
- 分離はポートではなく DB パスで行う

### 5.3 フォールバック

`use_memx=true` でも、以下の場合は `LocalAdapter` に落とす。

- API 未起動
- タイムアウト
- 接続拒否
- 初期ハンドシェイク失敗

---

## 6. データフロー

### 6.1 新規保存

```text
Open-Ark 内の機能
  -> MemoryAdapter.ingest(...)
    -> MemxAdapter
      -> memx API
        -> store DB
```

失敗時:

```text
Open-Ark 内の機能
  -> MemoryAdapter.ingest(...)
    -> MemxAdapter 失敗
      -> LocalAdapter
```

### 6.2 検索

```text
tool / prompt 構築
  -> MemoryAdapter.search(...)
    -> memx 検索 or 既存検索
```

---

## 7. フェーズ別の見え方

### Phase 1

- memx を「使えるようにする」
- 既存機能は残す

### Phase 2

- 一部の保存/検索導線を memx に寄せる
- 移行スクリプトや recall 導線を整える

### Phase 3

- 十分な移行確認後、旧実装の縮退を検討する

---

## 8. 注意点

### 8.1 今は Open-Ark の設計に集中する

OpenClaw からも同じ API を使えるのが理想だが、それは Open-Ark 側の Phase 1 の完了条件ではない。

### 8.2 旧実装削除は別イベント

削除判断には次が必要。

- 移行ツール
- 検索品質の比較
- ロールバック手順
- ユーザーへの移行確認

### 8.3 `auto_start_memx` は補助機能

便利ではあるが、memx 統合の成立条件ではない。  
まずは「既に起動している API に安全に接続できること」を優先する。

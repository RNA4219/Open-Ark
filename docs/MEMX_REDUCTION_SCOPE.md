# memx 統合後の削減スコープ整理

## 1. 目的

本書は、memx 統合後に Open-Ark のどの範囲を残し、どの範囲を削減対象とするかを整理するための共有資料である。

主目的は次の 3 つとする。

1. `削減後に残すコア範囲` を明確にする
2. `削減対象` と `削減対象だが blocker 判定に含めない範囲` を分ける
3. 削除シミュレーションや回帰テストが、repo 全体ではなく `残すべき範囲` を守るようにする

本書は、要件定義書そのものではなく、削減判断とテスト設計の境界条件をそろえる補助資料として扱う。

---

## 2. 前提

本資料は次の前提に立つ。

- memx 統合後の最終形は、Open-Ark 全体をそのまま維持する前提ではない
- 一部分のみを残して運用する構成を想定している
- そのため、現時点で repo 内に存在する全 import をそのまま削除阻害要因とみなしてはならない

特に重要なのは、`UI や上位統合導線が今 import している` という事実と、
`削減後にもその import が残るべき` という判断は同じではない、という点である。

---

## 3. スコープ分類

削減検討では、対象を次の 3 層に分けて扱う。

### 3.1 残存コア範囲

削減後にも残す前提の範囲。
この範囲で依存が壊れる場合は、削減 blocker とみなす。

対象:

- `memx` 系ツール群
- `MemxAdapter`
- `LocalAdapter`
- `memory_manager`
- `entity_tools`
- `memory_tools`
- Phase 2 / Phase 3 で定義した運用・移行・ロールバック導線

判断原則:

- ここが壊れるなら削減してはならない
- 削除シミュレーションの blocker 判定はまずこの範囲を守るために使う

### 3.2 削減対象範囲

memx 統合後に段階的縮退または削除を検討する範囲。

対象:

- `entity_memory_manager`
- `episodic_memory_manager`
- `rag_manager`
- `dreaming_manager_sync`
- `motivation_manager_sync`

補足:

- `dreaming_manager` と `motivation_manager` は本体と同期責務を分けて考える
- 本体ロジックまで捨てるのか、同期責務だけ外すのかは別途判断が必要

### 3.3 blocker 判定除外候補

現時点では削除候補を import していても、最終的にその範囲ごと整理または撤去する想定のもの。
この範囲は `現状依存している` だけで即 blocker とみなしてはならない。

代表例:

- `ui_handlers`
- `agent.graph`
- `alarm_manager`
- 画面導線や一時的な上位統合コード

判断原則:

- この範囲の import 残りは `整理対象` ではある
- ただし `残存コア範囲` の blocker と同じ重さでは扱わない
- 削除シミュレーションでは `参考情報` と `致命 blocker` を分けて報告する

---

## 4. テスト運用への反映

### 4.1 blocker 判定の基準

削除シミュレーションで `ModuleNotFoundError` が出た場合、次のように分類する。

#### blocker

残存コア範囲が削除候補へ依存している場合。

例:

- `entity_tools` が `entity_memory_manager` へ依存
- `memory_tools` が `rag_manager` へ依存
- `LocalAdapter` が旧実装依存のままで代替経路へ移れていない

#### 整理対象

UI、上位導線、将来撤去予定範囲が削除候補へ依存している場合。

例:

- `ui_handlers`
- `agent.graph`
- `alarm_manager`

### 4.2 テスト結果の読み方

削除シミュレーション結果は、少なくとも次の 2 系統に分けて出す。

1. `core blocker`
2. `non-core dependency`

こうすることで、
`UI が残っているから削減できない`
と
`コアがまだ旧実装に依存しているから削減できない`
を混同しないようにする。

### 4.3 優先順位

テストで最優先に守るべきなのは次である。

1. Phase 2 / Phase 3 の導線
2. memx / LocalAdapter のフォールバック
3. room 分離
4. ロールバック
5. 旧 UI や上位導線の整理

---

## 5. 現時点の想定

現時点では、次の理解を前提とする。

### 5.1 削減後にも残す想定

- `memx_tools`
- `memx_phase3`
- `MemxAdapter`
- `LocalAdapter`
- `memory_manager`
- `entity_tools`
- `memory_tools`
- Phase 2 / 3 の検収を通すために必要な最小導線

### 5.2 先に縮退・削減を検討する想定

- `entity_memory_manager`
- `episodic_memory_manager`
- `rag_manager`
- `dreaming_manager_sync`
- `motivation_manager_sync`

### 5.3 そのまま blocker に数えない想定

- フロント部分
- UI 層
- 旧上位統合導線
- 最終的に同時に整理する予定の周辺コード

---

## 6. 今後の使い方

### 6.1 テスト修正時

- 削除シミュレーションは `core blocker` と `non-core dependency` を分ける
- UI 依存を見つけても、即座に `削減不可` と判定しない

### 6.2 削減判断時

- `残存コア範囲` に依存が残っていなければ、削減候補を一段進められる
- `blocker 判定除外候補` は別チケットで整理する

### 6.3 報告時

削減阻害要因は次の形式で分けて報告する。

- `致命 blocker`: コア範囲の依存残り
- `整理対象`: UI / 上位導線の依存残り
- `未判断`: 本体と同期責務の切り分け未完了

---

## 7. 関連資料

- [MEMX_INTEGRATION_REQUIREMENTS.md](C:/Users/ryo-n/Codex_dev/Open-Ark/docs/MEMX_INTEGRATION_REQUIREMENTS.md)
- [MEMX_LEGACY_DELETION_CONTRACTS.md](C:/Users/ryo-n/Codex_dev/Open-Ark/docs/MEMX_LEGACY_DELETION_CONTRACTS.md)
- [MEMX_LEGACY_TEST_DESIGN.md](C:/Users/ryo-n/Codex_dev/Open-Ark/docs/MEMX_LEGACY_TEST_DESIGN.md)
- [MEMX_RUNBOOK.md](C:/Users/ryo-n/Codex_dev/Open-Ark/docs/MEMX_RUNBOOK.md)


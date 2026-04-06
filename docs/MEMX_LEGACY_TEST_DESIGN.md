# 旧記憶実装削減 テスト設計書

## 1. 目的

本書は、旧記憶実装の削減判断に先立ち、
削除候補機能に対するテスト設計を共有資料として整理したものである。

主目的は次の 3 つとする。

1. 削除候補ごとの振る舞い保証を、チーム内で共通認識にする
2. 「何をテストすれば削減判断できるか」を一覧化する
3. 削除前、削除中、削除後の各段階で壊れ方を検知できるようにする

本書は実装メモではなく、設計・レビュー・連携用の資料として扱う。

---

## 2. 対象

本書の対象は次の 5 系統とする。

1. `entity_memory_manager`
2. `episodic_memory_manager`
3. `rag_manager`
4. `dreaming_manager_sync` / `dreaming_manager` 周辺
5. `motivation_manager_sync` / `motivation_manager` 周辺

次は削除対象に含めず、存続前提とする。

- `memory_manager`
- `entity_tools`
- `memory_tools`
- `local_adapter`

---

## 3. テスト設計方針

### 3.1 基本方針

- 存在確認だけでなく、振る舞いの契約を固定する
- 旧実装と memx 代替経路の意味的一致を確認する
- `active` / `read_only` / `disabled` の状態差を確認する
- import 欠落や直接依存の残りを削除前に検知できるようにする
- Phase 2 / Phase 3 の検収を悪化させないことを確認する

### 3.2 テストの役割分類

| 種別 | 役割 |
|---|---|
| 契約テスト | 旧実装が満たしていた最低保証を固定する |
| 同値テスト | memx 代替経路が旧実装と意味的に同等か確認する |
| 状態テスト | `read_only` / `disabled` 時の期待挙動を固定する |
| 削除シミュレーション | import 欠落や依存残りを検知する |
| 回帰テスト | Phase 2 / Phase 3 の既存検収が崩れていないことを確認する |

### 3.3 判定基準

「削除してよい」と判断できるのは、少なくとも次を満たした対象に限る。

1. 契約テストがある
2. 同値テストがある
3. `disabled` 状態で主要導線が通る
4. import 欠落シミュレーションで想定外の直依存が残っていない
5. Phase 2 / Phase 3 の検収結果を悪化させない

---

## 4. テストファイル構成案

| ファイル | 主な役割 |
|---|---|
| `tests/test_legacy_contracts.py` | 削除候補ごとの契約テスト |
| `tests/test_legacy_equivalence.py` | 旧実装と memx 代替経路の同値テスト |
| `tests/test_legacy_disabled_mode.py` | `read_only` / `disabled` 状態の挙動確認 |
| `tests/test_legacy_deletion_simulation.py` | import 欠落と直依存の検知 |
| `tests/test_legacy_deletion_candidates.py` | 現状の回帰検知器と依存検出の補助基盤 |

---

## 5. テスト一覧

## 5.1 `entity_memory_manager`

### 契約テスト

| テスト名 | 確認内容 |
|---|---|
| `test_entity_contract_create_and_read` | 知識を保存し、同じ内容を再取得できる |
| `test_entity_contract_update_overwrites_or_appends` | 更新後に新しい内容が反映される |
| `test_entity_contract_list_contains_created_entities` | 一覧に作成済みエンティティが含まれる |
| `test_entity_contract_search_returns_relevant_entity` | 検索語に対応するエンティティが返る |
| `test_entity_contract_room_isolation` | 別 room から見えない |

### 同値テスト

| テスト名 | 確認内容 |
|---|---|
| `test_entity_equivalence_legacy_vs_memx_knowledge` | 旧実装と `memx_ingest/search/show` で意味的一致 |

### 状態テスト

| テスト名 | 確認内容 |
|---|---|
| `test_entity_disabled_mode_keeps_primary_paths_alive` | `disabled` 相当でも代替導線が成立する |
| `test_entity_read_only_mode_preserves_read_paths` | `read_only` 相当で参照系だけ残る |

### 削除シミュレーション

| テスト名 | 確認内容 |
|---|---|
| `test_entity_import_missing_fails_loudly` | import 欠落時に依存残りを検出する |

---

## 5.2 `episodic_memory_manager`

### 契約テスト

| テスト名 | 確認内容 |
|---|---|
| `test_episode_contract_store_and_load` | エピソード保存後に取得できる |
| `test_episode_contract_latest_date_available` | 最新日時取得が壊れない |
| `test_episode_contract_context_contains_recent_episode` | 文脈取得に直近エピソードが反映される |
| `test_episode_contract_room_isolation` | room 混線がない |

### 同値テスト

| テスト名 | 確認内容 |
|---|---|
| `test_episode_equivalence_legacy_vs_memx_journal` | 旧実装と `memx_ingest/search/recall` の意味的一致 |

### 状態テスト

| テスト名 | 確認内容 |
|---|---|
| `test_episode_disabled_mode_keeps_context_paths_alive` | `disabled` でも周辺導線が成立する |
| `test_episode_read_only_mode_preserves_history_access` | `read_only` で履歴参照が維持される |

### 削除シミュレーション

| テスト名 | 確認内容 |
|---|---|
| `test_episode_import_missing_detects_dependency` | import 欠落を検出する |

---

## 5.3 `rag_manager`

### 契約テスト

| テスト名 | 確認内容 |
|---|---|
| `test_rag_contract_query_returns_context_or_empty` | 異常終了せず結果または空を返す |
| `test_rag_contract_knowledge_search_path_alive` | 知識検索導線が成立する |
| `test_rag_contract_room_isolation` | room 分離が保たれる |

### 同値テスト

| テスト名 | 確認内容 |
|---|---|
| `test_rag_equivalence_legacy_vs_memx_recall` | 旧 RAG と `memx_recall` の意味的一致 |

### 状態テスト

| テスト名 | 確認内容 |
|---|---|
| `test_rag_disabled_mode_keeps_search_paths_alive` | `disabled` でも検索主要導線が生きる |
| `test_rag_read_only_mode_keeps_context_reading_alive` | `read_only` で参照系が維持される |

### 削除シミュレーション

| テスト名 | 確認内容 |
|---|---|
| `test_rag_import_missing_does_not_break_startup` | import 欠落時に致命障害を検出する |

---

## 5.4 `dreaming_manager_sync` / `dreaming_manager`

### 契約テスト

| テスト名 | 確認内容 |
|---|---|
| `test_dream_contract_store_and_reload_insight` | 洞察保存後に再取得できる |
| `test_dream_contract_recent_insights_available` | 最近の洞察取得が成立する |
| `test_dream_contract_sync_failure_is_nonfatal` | 同期失敗でも本体が落ちない |

### 同値テスト

| テスト名 | 確認内容 |
|---|---|
| `test_dream_equivalence_legacy_vs_memx_journal_sync` | journal 側代替で意味的一致 |

### 状態テスト

| テスト名 | 確認内容 |
|---|---|
| `test_dream_disabled_mode_keeps_dream_flow_alive` | `disabled` でも夢生成導線が残る |
| `test_dream_read_only_mode_preserves_insight_access` | `read_only` で洞察参照が維持される |

### 削除シミュレーション

| テスト名 | 確認内容 |
|---|---|
| `test_dream_import_missing_detects_hidden_dependency` | import 欠落時の隠れ依存を検知する |

---

## 5.5 `motivation_manager_sync` / `motivation_manager`

### 契約テスト

| テスト名 | 確認内容 |
|---|---|
| `test_motivation_contract_add_and_read_question` | 未解決問いを追加して読める |
| `test_motivation_contract_resolve_question_changes_state` | 解決後に状態が変わる |
| `test_motivation_contract_internal_state_available` | 内部状態取得が成立する |
| `test_motivation_contract_room_isolation` | room 分離が保たれる |

### 同値テスト

| テスト名 | 確認内容 |
|---|---|
| `test_motivation_equivalence_legacy_vs_memx_short` | 旧実装と `memx_ingest/recall/resolve` の意味的一致 |

### 状態テスト

| テスト名 | 確認内容 |
|---|---|
| `test_motivation_disabled_mode_keeps_core_logic_alive` | `disabled` でも本体ロジックが残る |
| `test_motivation_read_only_mode_preserves_question_reading` | `read_only` で参照系が維持される |

### 削除シミュレーション

| テスト名 | 確認内容 |
|---|---|
| `test_motivation_import_missing_detects_dependency` | import 欠落を検出する |

---

## 6. 共通削除シミュレーション

削除候補ごとの個別テストに加え、共通で次を用意する。

| テスト名 | 確認内容 |
|---|---|
| `test_disabled_targets_do_not_break_phase2_acceptance_subset` | `disabled` 相当でも Phase 2 主要導線が保たれる |
| `test_disabled_targets_do_not_break_phase3_acceptance_subset` | `disabled` 相当でも Phase 3 主要導線が保たれる |
| `test_missing_module_simulation_fails_on_remaining_direct_imports` | 想定外の直接 import が残っていれば失敗する |
| `test_surviving_components_still_handle_fallback` | 存続対象がフォールバック責務を維持する |
| `test_memx_paths_cover_deleted_capabilities` | memx 側代替導線が主要能力をカバーする |

---

## 7. pytest マーカー設計

テストの意図を共有しやすくするため、次のマーカーを推奨する。

| マーカー | 用途 |
|---|---|
| `contract` | 契約テスト |
| `equivalence` | 同値テスト |
| `disabled_mode` | `read_only` / `disabled` 状態テスト |
| `deletion_simulation` | import 欠落や削除シミュレーション |
| `real_api` | 実 API 前提テスト |

---

## 8. 運用上の読み方

### 8.1 削除前

- 契約テストと同値テストを先に作る
- `disabled` 運用で壊れないか確認する

### 8.2 削除判断時

- この文書の対象テストが揃っているか確認する
- Phase 2 / Phase 3 検収を悪化させていないか確認する

### 8.3 削除後

- `DELETION_OK_EVIDENCE` 系は pass のまま維持する
- `DELETION_BREAKAGE_DETECTOR` 系は、役割を終えたものを整理するか、
  「削除済みを確認するテスト」へ置き換える

---

## 9. 関連資料

- [MEMX_LEGACY_DELETION_CONTRACTS.md](C:/Users/ryo-n/Codex_dev/Open-Ark/docs/MEMX_LEGACY_DELETION_CONTRACTS.md)
- [MEMX_INTEGRATION_REQUIREMENTS.md](C:/Users/ryo-n/Codex_dev/Open-Ark/docs/MEMX_INTEGRATION_REQUIREMENTS.md)
- [MEMX_RUNBOOK.md](C:/Users/ryo-n/Codex_dev/Open-Ark/docs/MEMX_RUNBOOK.md)
- [test_legacy_deletion_candidates.py](C:/Users/ryo-n/Codex_dev/Open-Ark/app/tests/test_legacy_deletion_candidates.py)


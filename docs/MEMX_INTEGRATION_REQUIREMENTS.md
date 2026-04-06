# memx-resolver 統合要件定義

## 1. 文書の位置づけ

本書は、Open-Ark に対する `memx-resolver` 統合の要件定義書である。  
実装案、作業順、運用手順ではなく、「何を満たせば統合が成立したと見なすか」を定義する。

本書の優先順位は次の通り。

1. Open-Ark の既存利用者が破壊的変更なしで使い続けられること
2. `memx-resolver` を独立サービスとして疎結合で利用できること
3. 将来の完全移行に向けた段階移行が可能であること

本書は Open-Ark を主語とする。  
OpenClaw や他クライアントとの連携可能性は考慮するが、Phase 1 の成立条件には含めない。

---

## 2. 用語定義

| 用語 | 定義 |
|---|---|
| Open-Ark | 本 repo の Python アプリケーション |
| memx-resolver | Open-Ark が外部利用する独立 API サービス |
| room | Open-Ark における人格・セッション単位のデータ領域 |
| room_dir | 各 room の実ディレクトリ。Open-Ark の実行ディレクトリ基準では `characters/<room_name>` |
| Adapter | Open-Ark から見た記憶アクセス抽象層 |
| MemxAdapter | `memx-resolver` API を用いる Adapter 実装 |
| LocalAdapter | 既存記憶機構を用いる Adapter 実装 |
| fallback | memx 利用ができない場合に LocalAdapter へ退避して継続動作すること |
| Phase 1 | 接続基盤、Adapter、基本ツール導入まで |
| Phase 2 | 検索導線拡張、移行補助、resolver/GC 検討まで |
| Phase 3 | 完全移行可否の判断と旧実装縮退の検討 |

---

## 3. 対象範囲

### 3.1 本書の対象

- Open-Ark から `memx-resolver` API を利用するための要件
- Open-Ark 内の記憶アクセス抽象化要件
- room ごとのデータ分離要件
- 既存記憶機構との互換性要件
- 失敗時の継続動作要件

### 3.2 本書の対象外

- OpenClaw plugin の詳細仕様
- `typed_ref` 正規化の詳細仕様
- Tracker 連携の詳細仕様
- Context Rebuild の詳細仕様
- memx サーバー内部実装の変更要求
- Phase 1 時点での既存記憶ファイル削除

---

## 4. 現状認識

Open-Ark には既に複数の記憶管理経路が存在する。

| 機能領域 | 主要実装 | 主な役割 |
|---|---|---|
| エンティティ記憶 | `app/entity_memory_manager.py` | 人物・概念の永続知識 |
| エピソード記憶 | `app/episodic_memory_manager.py` | 高重要イベントの保存 |
| 問い管理 | `app/motivation_manager.py` | 好奇心ドライブと未解決の問い |
| 洞察・夢 | `app/dreaming_manager.py` | 内省、夢、洞察の生成と保存 |
| 記憶検索 | `app/rag_manager.py` | 過去ログや関連記憶の検索 |

このため、memx 統合は「新規機能追加」であると同時に、「複数の既存経路を安全に束ねる」作業でもある。

---

## 5. 統合目的

統合目的は次の 4 つとする。

1. 記憶の保存、検索、参照の API を一本化できる状態を作る
2. `short` / `journal` / `knowledge` / `archive` の 4 層構造へ対応できる状態を作る
3. `memx-resolver` 障害時にも Open-Ark が継続動作できる状態を作る
4. 既存実装を即時削除せず、段階移行可能な状態を作る

---

## 6. 設計制約

### 6.1 疎結合制約

| ID | 要件 |
|---|---|
| CONSTRAINT-001 | Open-Ark は `memx-resolver` を外部 API として利用しなければならない |
| CONSTRAINT-002 | Open-Ark は `memx-resolver` の内部 DB 構造へ直接依存してはならない |
| CONSTRAINT-003 | memx 連携の有無は設定で切り替え可能でなければならない |

### 6.2 room 分離制約

| ID | 要件 |
|---|---|
| CONSTRAINT-004 | room 分離はポートではなく DB パスで実現しなければならない |
| CONSTRAINT-005 | 異なる room の記憶が同じ DB パスへ混在してはならない |
| CONSTRAINT-006 | DB パスは room から決定可能でなければならない |

### 6.3 互換性制約

| ID | 要件 |
|---|---|
| CONSTRAINT-007 | Phase 1 で既存の主要記憶機能を削除してはならない |
| CONSTRAINT-008 | memx 未使用時の既存動作を維持しなければならない |
| CONSTRAINT-009 | memx 接続失敗を理由に Open-Ark 全体の起動を失敗させてはならない |

---

## 7. 機能要件

### 7.1 設定

| ID | 要件 |
|---|---|
| FR-001 | Open-Ark は memx 利用有無を設定で制御できなければならない |
| FR-002 | Open-Ark は memx API アドレスを設定で指定できなければならない |
| FR-003 | Open-Ark は room ごとの DB パステンプレートを設定で指定できなければならない |
| FR-004 | API アドレスは環境変数で上書きできなければならない |
| FR-005 | 設定の正本は Open-Ark の実行設定ファイルでなければならない |

設定値の論理名:

- `use_memx`
- `memx_api_addr`
- `memx_db_path_template`
- `memx_request_timeout_sec`
- `auto_start_memx` は任意の補助設定とする

### 7.2 Adapter 抽象化

| ID | 要件 |
|---|---|
| FR-006 | Open-Ark は記憶アクセスを Adapter 経由で扱わなければならない |
| FR-007 | Adapter は少なくとも `ingest`、`search`、`show` を提供しなければならない |
| FR-008 | Open-Ark は `MemxAdapter` と `LocalAdapter` の 2 系統を持たなければならない |
| FR-009 | Adapter の選択は呼び出し側に分散させず、1 箇所に集約しなければならない |

### 7.3 memx API 利用

| ID | 要件 |
|---|---|
| FR-010 | Open-Ark は `notes:ingest` を呼び出せなければならない |
| FR-011 | Open-Ark は `notes:search` を呼び出せなければならない |
| FR-012 | Open-Ark は `GET /v1/notes/{id}` を呼び出せなければならない |
| FR-013 | Open-Ark は room に対応する DB パスを決定できなければならない |
| FR-014 | API 呼び出しはタイムアウト設定を持たなければならない |

### 7.4 フォールバック

| ID | 要件 |
|---|---|
| FR-015 | `use_memx=true` でも API 未到達時は LocalAdapter にフォールバックしなければならない |
| FR-016 | フォールバック時も Open-Ark の主要操作は継続可能でなければならない |
| FR-017 | フォールバック発生はログまたは追跡可能な形で記録されなければならない |

フォールバック対象の最低条件:

- 接続拒否
- タイムアウト
- 名前解決失敗
- 初期接続確認失敗

### 7.5 ストア対応

| ID | 要件 |
|---|---|
| FR-018 | Open-Ark は `short` / `journal` / `knowledge` / `archive` の 4 ストアを論理的に扱えなければならない |
| FR-019 | 未解決の問いと一時メモは `short` に対応づけられなければならない |
| FR-020 | エピソード、夢、洞察、進捗は `journal` に対応づけられなければならない |
| FR-021 | エンティティ知識と確定事実は `knowledge` に対応づけられなければならない |
| FR-022 | 退避済み記憶は `archive` に対応づけられなければならない |

### 7.6 Open-Ark への導入範囲

| ID | 要件 |
|---|---|
| FR-023 | Open-Ark は `memx_ingest`、`memx_search`、`memx_show` の基本ツールを提供しなければならない |
| FR-024 | 既存ツールは Phase 1 で削除してはならない |
| FR-025 | `DreamingManager` と `MotivationManager` に対し、将来 memx 経由保存を差し込める設計でなければならない |
| FR-026 | 既存 room データは Phase 1 で破壊してはならない |

### 7.7 Phase 2 機能要求

Phase 2 の機能要求は、Phase 1 の接続基盤を前提に、検索導線、resolver 導線、GC 導線、移行補助導線を追加対象とする。  
本節の要件を基に、`10.3 Phase 2 受け入れ条件` と `10.4 Phase 2 不合格条件` を正式条件として適用する。

#### 7.7.1 検索導線

| ID | 要件 |
|---|---|
| FR-P2-001 | Open-Ark は `memx_recall` 相当の導線を提供しなければならない |
| FR-P2-002 | `memx_recall` は少なくとも `recent` / `relevant` / `related` の mode を扱えなければならない |
| FR-P2-003 | `memx_recall` は memx 利用可能時に resolver / recall API を優先利用しなければならない |
| FR-P2-004 | `memx_recall` は memx 利用不可時に LocalAdapter ベースの検索へフォールバックしなければならない |
| FR-P2-005 | `memx_recall` の返却結果は、AI が後続推論に利用できる整形済みコンテキストでなければならない |

#### 7.7.2 resolver 導線

| ID | 要件 |
|---|---|
| FR-P2-006 | Open-Ark はノートのライフサイクル操作を行う `memx_resolve` 相当の導線を提供しなければならない |
| FR-P2-007 | `memx_resolve` は少なくとも `promote` / `archive` / `link` / `summarize` の action を扱えなければならない |
| FR-P2-008 | resolver 導線は `short` から `knowledge`、`journal` から `archive` などのストア間遷移を明示的に扱えなければならない |
| FR-P2-009 | resolver 導線は note ID、元 store、action、必要に応じて target store や entity 情報を指定できなければならない |
| FR-P2-010 | resolver 導線は manager 内部から暗黙に自動実行してはならず、少なくとも Phase 2 では明示的な tool / API 呼び出しとして扱わなければならない |

#### 7.7.3 GC 導線

| ID | 要件 |
|---|---|
| FR-P2-011 | Open-Ark は memx 側 GC を呼び出す `memx_gc` 相当の導線を提供しなければならない |
| FR-P2-012 | GC は `dry-run` と `execute` を明確に分離して扱わなければならない |
| FR-P2-013 | `dry-run` は削除候補、件数、理由、安全確認結果を返さなければならない |
| FR-P2-014 | `execute` は設定で明示的に有効化されていない限り実行してはならない |
| FR-P2-015 | GC 導線は対象 store、年齢条件、アクセス頻度条件、除外タグ等のスコープを指定できなければならない |
| FR-P2-016 | Open-Ark は Phase 2 で `knowledge` の重要記憶や既存ローカル資産を GC の自動削除対象としてはならない |

#### 7.7.4 移行補助導線

| ID | 要件 |
|---|---|
| FR-P2-017 | Open-Ark は既存データを memx へ移行する補助導線を提供しなければならない |
| FR-P2-018 | 移行補助導線は少なくとも `preview` と `migrate` の 2 mode を扱えなければならない |
| FR-P2-019 | `preview` は移行候補の一覧、件数、対象 store、マッピング結果を返さなければならない |
| FR-P2-020 | `migrate` は移行元ファイルを既定で保持しなければならない |
| FR-P2-021 | 移行補助導線は `entity_memory` / `episode` / `question` / `insight` など既存データ種別を識別して扱えなければならない |
| FR-P2-022 | 移行補助導線は room 単位で実行され、他 room のデータを混在させてはならない |

#### 7.7.5 既存機構との接続

| ID | 要件 |
|---|---|
| FR-P2-023 | `DreamingManager` は洞察・夢・発見エピソードのうち、Phase 2 で許可された経路のみ memx journal へ同期できなければならない |
| FR-P2-024 | `MotivationManager` は未解決の問いを memx short へ同期できなければならない |
| FR-P2-025 | `entity_tools` / `memory_tools` と memx 系ツールの責務分界は明示されなければならない |
| FR-P2-026 | Phase 2 では既存導線を全面置換してはならず、並行運用または段階置換可能な構成を維持しなければならない |

### 7.8 Phase 3 機能要求

Phase 3 の機能要求は、Phase 2 までで整備された導線と移行補助を前提に、旧実装の縮退、完全移行可否の判断、高度 resolver 機能の統合を対象とする。  
本節の要件を基に、`10.5 Phase 3 受け入れ条件` と `10.6 Phase 3 不合格条件` を正式条件として適用する。

#### 7.8.1 旧実装の縮退

| ID | 要件 |
|---|---|
| FR-P3-001 | Open-Ark は旧記憶実装のうち、memx へ置換済みの導線を段階的に縮退または無効化できなければならない |
| FR-P3-002 | 縮退対象と存続対象は機能単位で明示されなければならない |
| FR-P3-003 | 旧実装の縮退は room 単位の既存データを破壊せずに実施できなければならない |
| FR-P3-004 | 旧実装を縮退した後も、必要な read-only 参照または移行補助経路は保持されなければならない |

#### 7.8.2 完全移行判断

| ID | 要件 |
|---|---|
| FR-P3-005 | Open-Ark は memx を主要導線として扱えるかどうかを判定できなければならない |
| FR-P3-006 | 完全移行判断には、少なくとも recall / resolve / gc / migrate / fallback の検証結果が反映されなければならない |
| FR-P3-007 | 完全移行判断は「移行可」「暫定並行運用」「移行不可」のように可否と理由を残せなければならない |
| FR-P3-008 | 完全移行判断の前に、ロールバック手段と既存データ保全手段が確認されていなければならない |

#### 7.8.3 高度 resolver 統合

| ID | 要件 |
|---|---|
| FR-P3-009 | Open-Ark は Phase 2 より高度な resolver 系機能を、必要に応じて追加統合できなければならない |
| FR-P3-010 | 高度 resolver 統合は、既存 tool / manager の責務を壊さない形で差し込まれなければならない |
| FR-P3-011 | 高度 resolver 統合は、明示的な導線または制御条件なしに自動有効化してはならない |
| FR-P3-012 | 高度 resolver 統合の失敗時も、Phase 2 水準の基本導線へ安全に退避できなければならない |

#### 7.8.4 運用と可逆性

| ID | 要件 |
|---|---|
| FR-P3-013 | Phase 3 の変更は、設定または手順により旧構成へロールバック可能でなければならない |
| FR-P3-014 | 旧実装削除または無効化の前に、影響範囲、代替導線、復旧手順が文書化されていなければならない |
| FR-P3-015 | Phase 3 の移行結果は room 単位に追跡可能でなければならない |
| FR-P3-016 | Phase 3 完了後も、既存利用者が段階的に追随できる移行案内が存在しなければならない |

---

## 8. 非機能要件

### 8.1 可用性

| ID | 要件 |
|---|---|
| NFR-001 | memx 利用可否にかかわらず Open-Ark は起動可能でなければならない |
| NFR-002 | memx 障害時も既存機能による限定継続運用が可能でなければならない |

### 8.2 後方互換性

| ID | 要件 |
|---|---|
| NFR-003 | `use_memx=false` のとき、既存利用者の基本動作は従来と同等でなければならない |
| NFR-004 | memx 導入前に作成された room でも起動可能でなければならない |

### 8.3 観測可能性

| ID | 要件 |
|---|---|
| NFR-005 | memx 接続成功、失敗、フォールバックを識別できるログを出力できなければならない |
| NFR-006 | room ごとの DB パス決定結果を追跡可能でなければならない |

### 8.4 安全性

| ID | 要件 |
|---|---|
| NFR-007 | 異なる room 間で記憶の混線を発生させてはならない |
| NFR-008 | Phase 1 では既存記憶データの自動削除を行ってはならない |
| NFR-009 | 明示的な移行確認なしに既存ファイルを memx 正本へ切り替えてはならない |

---

## 9. Phase 定義

### 9.1 Phase 1

Phase 1 の完了条件は次の通り。

- 設定で memx 利用を切り替えられる
- Adapter 層が存在する
- `ingest/search/show` を memx API へ接続できる
- API 障害時に LocalAdapter で継続動作できる
- 既存機能を削除していない

### 9.2 Phase 2

Phase 2 の対象は次の通り。

- `memx_recall` 等の検索導線追加
- `docs:resolve` など resolver 系導線の検討
- GC の dry-run / execute 方針整理
- 既存データ移行手段の追加

Phase 2 は Phase 1 の完了後にのみ着手可能とする。

### 9.2.1 Phase 2 実装前チェックリスト

Phase 2 は検索導線、resolver、GC、移行補助など、既存データへの副作用や責務衝突を起こしやすい領域を含む。  
このため、実装着手前に次のチェックを完了していなければならない。

| No. | チェック項目 | 意図 | 目的 |
|---|---|---|---|
| 1 | Phase 2 で追加する API 契約を確定する | `docs:resolve`、GC、移行補助の request / response / error を曖昧なまま実装すると、Open-Ark 側だけが先行して不整合を起こしやすいため | Open-Ark 実装が memx-resolver の実契約と整合した状態で着手できるようにする |
| 2 | resolver 系機能の対象範囲を確定する | `docs:resolve` をどのツールや manager から呼ぶかが曖昧だと、責務の重複や二重導線が発生しやすいため | Phase 2 で実装する resolver 導線を限定し、影響範囲を制御する |
| 3 | GC の実行モードを `dry-run` と `execute` で分離して定義する | GC は誤実行時の影響が大きく、確認なしに実行可能にすると既存記憶や memx 側データを毀損するため | まず安全な観測モードを成立させ、実削除系の導入条件を明確にする |
| 4 | GC の禁止事項を明文化する | 「何を消してよいか」より先に「何を消してはいけないか」を定めないと、Phase 2 の安全性が崩れるため | 既存の entity / episode / question 系資産と memx の重要記憶を誤削除対象から守る |
| 5 | 既存記憶機構との責務分界を確定する | `DreamingManager`、`MotivationManager`、`entity_tools`、`memory_tools` が同じ情報を別経路で扱うと、保存先の重複や参照不整合が起きやすいため | 「どの情報をどこへ保存し、どこから読むか」を明確にし、導線競合を防ぐ |
| 6 | 移行対象データと非対象データを明確にする | 何を移行し、何を残置するかが曖昧だと、移行スクリプト要件もロールバック条件も定義できないため | Phase 2 の移行補助を限定的かつ可逆なものとして設計できるようにする |
| 7 | ロールバック方針を定義する | 移行補助や resolver 連携で想定外の結果が出たとき、復旧手段がないと Phase 2 の試行自体が危険になるため | 問題発生時に `use_memx=false` や旧導線へ安全に戻せる状態を保つ |
| 8 | Phase 2 の観測ログ項目を確定する | resolver 呼び出し、GC 判定、移行 dry-run の結果が追えないと、不具合原因の切り分けが困難になるため | 導線追加後も、room 単位・操作単位で挙動を追跡可能にする |
| 9 | 実 API を使う統合確認の最小セットを定義する | Phase 1 まではモック中心で成立したが、Phase 2 は副作用が増えるためモックだけでは安全性を担保しづらいため | 少なくとも resolver 呼び出し、GC dry-run、fallback 維持を実サーバー相手に検証できるようにする |
| 10 | Phase 2 完了条件と不合格条件を先に定義する | 実装開始後に完了条件を考えると、機能追加が先行して検収観点が後追いになりやすいため | 実装の前に「どこまでやれば完了か」「何が起きたら未達か」を判定可能にする |

実装着手可否の判断基準:

- 上記 10 項目のうち 1〜4 が未確定なら、Phase 2 実装に着手してはならない
- 5〜8 が未確定なら、manager / tool への本接続は保留し、調査または要件確定を優先しなければならない
- 9〜10 が未確定なら、試験導入はできても Phase 2 完了を宣言してはならない

### 9.3 Phase 3

Phase 3 では次を検討対象とする。

- 旧実装の縮退または削除
- 完全移行可否の判断
- 高度 resolver 機能の統合

Phase 3 に進む前提:

- Phase 2 までの受け入れ条件を満たしていること
- 移行手段とロールバック手段が存在すること
- 旧実装削除の影響範囲が把握されていること

### 9.3.1 Phase 3 実装前チェックリスト

Phase 3 は旧実装の縮退や完全移行判断を含むため、Phase 1・2 よりも破壊的影響の可能性が高い。  
このため、実装着手前に次のチェックを完了していなければならない。

| No. | チェック項目 | 意図 | 目的 |
|---|---|---|---|
| 1 | Phase 2 の Real API 検収を完了する | Phase 2 の実運用妥当性が未確認のまま旧実装を畳むと、退避先のない不安定構成になるため | Phase 3 の前提として、memx 主要導線の実用性を確認する |
| 2 | 縮退対象の旧実装一覧を確定する | 削る対象が曖昧なまま実装すると、必要な read path や移行補助まで失う危険があるため | 何を残し、何を畳むかを先に明文化する |
| 3 | ロールバック手順を実地確認する | 手順だけ存在しても実際に戻せないなら、完全移行判断の安全性が担保できないため | 旧構成へ戻せることを事前に検証する |
| 4 | 旧データ参照の必要性を評価する | 完全移行後も、監査・比較・再移行のため旧データ参照が必要な場合があるため | 削除ではなく read-only 化で足りる箇所を見極める |
| 5 | 完全移行判断の判定項目を固定する | 感覚的に『もう大丈夫そう』で進めると後から基準がぶれるため | 移行可否を定量・定性の両面で判定できるようにする |
| 6 | 高度 resolver 機能の有効化条件を定義する | 高機能を既定で有効にすると、Phase 2 水準の安定導線まで巻き込んで不安定化するため | 段階的有効化と安全退避を両立する |
| 7 | 既存利用者向け移行案内を準備する | 実装だけ先行すると、利用者はどの設定を変えればよいか分からず混乱するため | 段階移行を現実的に進められるようにする |
| 8 | Phase 3 完了条件と不合格条件を先に固定する | 旧実装削除は戻しにくいため、後から検収観点を作るやり方が特に危険であるため | 何をもって『完全移行可』と判断するかを先に確定する |

実装着手可否の判断基準:

- 上記 8 項目のうち 1〜3 が未完了なら、Phase 3 実装に着手してはならない
- 4〜6 が未確定なら、旧実装の縮退や高度 resolver の本有効化を行ってはならない
- 7〜8 が未確定なら、Phase 3 完了を宣言してはならない

---

## 10. 受け入れ条件

### 10.1 Phase 1 受け入れ条件

| ID | 条件 |
|---|---|
| AC-001 | `use_memx=true` かつ memx API 正常時に `memx_ingest` が成功する |
| AC-002 | `use_memx=true` かつ memx API 正常時に `memx_search` が結果を返せる |
| AC-003 | `use_memx=true` かつ memx API 正常時に `memx_show` が対象ノートを返せる |
| AC-004 | `use_memx=true` かつ memx API 停止時でも Open-Ark が起動に成功する |
| AC-005 | `use_memx=true` かつ memx API 停止時に LocalAdapter へ退避できる |
| AC-006 | `use_memx=false` で従来の主要機能が継続利用できる |
| AC-007 | 異なる room で書き込んだ記憶が同一 DB パスへ混在しない |
| AC-008 | memx 導入後も既存の entity / episode / question 系データが自動削除されない |

### 10.2 不合格条件

次のいずれかを満たす場合、Phase 1 は未達とする。

- memx API 未起動時に Open-Ark が起動不能になる
- room を切り替えても同一 DB へ保存される
- `use_memx=false` で既存主要機能が失われる
- 既存記憶ファイルが自動削除される

### 10.3 Phase 2 受け入れ条件

以下を Phase 2 の正式な受け入れ条件とする。

| ID | 条件 |
|---|---|
| AC-P2-001 | memx 利用可能時に `memx_recall` が `recent` / `relevant` / `related` の少なくとも 1 mode で結果を返せる |
| AC-P2-002 | memx 利用不可時に `memx_recall` が LocalAdapter 系検索へフォールバックし、エラー終了ではなく空または代替結果を返せる |
| AC-P2-003 | `memx_resolve` が `promote` により `short` から `knowledge` への解決操作を実行できる |
| AC-P2-004 | `memx_resolve` が `archive` により `journal` から `archive` への解決操作を実行できる |
| AC-P2-005 | `memx_gc` の `dry-run` が削除候補、件数、理由、安全確認結果を返せる |
| AC-P2-006 | `memx_gc` の `execute` は `gc_execute_enabled=true` の明示設定なしでは実行拒否される |
| AC-P2-007 | `memx_gc` は `stores`、`age_days_min`、`exclude_tags` 等のスコープ条件を受け付けられる |
| AC-P2-008 | 移行補助の `preview` が候補一覧、件数、target store、マッピング結果を返せる |
| AC-P2-009 | 移行補助の `migrate` は既定で source file を削除せず、移行後も元データを保持する |
| AC-P2-010 | 移行補助は room 単位で動作し、他 room の候補を混在させない |
| AC-P2-011 | `DreamingManager` / `MotivationManager` の Phase 2 接続は memx 無効時に既存導線を壊さず継続利用できる |
| AC-P2-012 | resolver / GC / migrate の各導線は room、mode、action、結果を追跡可能なログまたは同等の観測情報を出せる |

### 10.4 Phase 2 不合格条件

次のいずれかを満たす場合、Phase 2 は未達とする。

- `memx_recall` が memx 利用不可時に即失敗し、LocalAdapter へ退避できない
- `memx_resolve` が store 間遷移を実行できない、または不正な action を黙って受理する
- `memx_gc` が `dry-run` と `execute` を区別せず、確認なしに削除系操作を行える
- `gc_execute_enabled=false` でも `execute` が実行できてしまう
- `knowledge` の重要記憶や既存ローカル資産が GC や移行処理で削除される
- `migrate` 実行時に source file が既定で失われる
- room をまたいで resolver / GC / migrate の対象が混在する
- `DreamingManager` / `MotivationManager` への接続により、既存導線のみの運用が壊れる
- Phase 2 の各導線について、実 API またはそれに準ずる経路での検証根拠が存在しない

### 10.5 Phase 3 受け入れ条件

以下を Phase 3 の正式な受け入れ条件とする。

| ID | 条件 |
|---|---|
| AC-P3-001 | 縮退対象として定義された旧記憶導線が、設定または明示手順に従って無効化または read-only 化できる |
| AC-P3-002 | 旧実装縮退後も、必要な参照・移行補助・ロールバックに必要な最低限の経路が維持される |
| AC-P3-003 | 完全移行判断が、検証結果と理由を伴って `移行可` / `暫定並行運用` / `移行不可` のいずれかで記録される |
| AC-P3-004 | 完全移行判断に、Phase 2 の Real API 検証結果と fallback 検証結果が反映されている |
| AC-P3-005 | 高度 resolver 機能は、明示的な有効化条件の下でのみ利用可能になる |
| AC-P3-006 | 高度 resolver 機能の失敗時に、Phase 2 水準の基本導線へ退避できる |
| AC-P3-007 | 旧構成へのロールバック手順が存在し、少なくとも 1 回は再現確認されている |
| AC-P3-008 | room 単位のデータ保全状態と移行状態が追跡可能である |
| AC-P3-009 | 既存利用者向けに、設定変更点、互換性差分、復旧手順を含む移行案内が存在する |
| AC-P3-010 | Phase 3 実施後も、明示対象外の room や既存データが破壊されていない |

### 10.6 Phase 3 不合格条件

次のいずれかを満たす場合、Phase 3 は未達とする。

- Phase 2 の Real API 検証が未完了のまま、旧実装の縮退または削除を進める
- 縮退後に旧データ参照、移行補助、またはロールバックに必要な経路まで失われる
- 完全移行判断が主観的説明だけで、検証結果や理由を伴わない
- 高度 resolver 機能が既定で有効になり、失敗時に基本導線へ戻れない
- ロールバック手順が存在しない、または再現確認されていない
- room をまたいだ影響や既存データの破壊が発生する
- 利用者に必要な移行案内がなく、既存運用から追随できない

---

## 11. 保留事項

以下は要件として確定させず、後続検討とする。

- `db_path` を API 起動時に固定するか、リクエスト単位で渡すか
- embeddings、FTS、ハイブリッド検索の内部仕様
- `short` から `knowledge` への昇格ルール
- GC の閾値
- `auto_start_memx` の実装有無

保留事項は Phase 1 の成立条件には含めない。

---

## 12. 実装状態（2026-04-06 時点）

### 12.1 Phase 完了状況

| Phase | 状態 | 備考 |
|---|---|---|
| Phase 1 | 完了 | Adapter層、基本ツール、フォールバック |
| Phase 2 | 完了 | recall/resolve/gc/migrate 導線 |
| Phase 3 | 完了 | 縮退制御、移行判断、高度 resolver（実験的） |

### 12.2 テスト結果

**Real API なし**:
- Phase 2: `24 passed, 6 skipped`
- Phase 3: `13 passed, 1 skipped`
- 合算: `37 passed, 7 skipped`

**Real API あり**:
- Phase 2: `30 passed`
- Phase 3: `14 passed`
- 合算: `44 passed`

### 12.3 旧実装の扱い

**削除済みコンポーネント**（`DELETED_COMPONENTS` で履歴管理）:
- `entity_memory_manager` - deleted（`entity_tools` / `memx_ingest(store="knowledge")` へ置換）
- `episodic_memory_manager` - deleted（`memx_ingest(store="journal")` / `memx_recall` へ置換）
- `rag_manager` - deleted（`memx_search` / `memx_recall` へ置換）
- `dreaming_manager_sync` - deleted（同期なし運用）
- `motivation_manager_sync` - deleted（同期なし運用）

**存続対象**（縮退しない）:
- `memory_manager` - LocalAdapter 動作に必要
- `entity_tools` - memx 無効時の代替導線
- `memory_tools` - 後方互換性維持
- `local_adapter` - フォールバック先として必須

### 12.4 未実装・次回課題

- 高度 resolver 機能の本格有効化（現在は実験的）
- UI / 実依存を含む統合確認の整理
- CI への Real API テスト自動組み込み

---

## 13. 参照資料

- `docs/AUTO_RESOLVE_AND_CONVERT_IMPL.md`
- `docs/MEMX_SURVEY_RESULTS.md`
- `docs/NEXUS_ARK_SPECIFICATION.md`
- `docs/MEMX_RUNBOOK.md` - 運用手順
- `app/tests/test_memx_phase2.py` - Phase 2 テスト
- `app/tests/test_memx_phase3.py` - Phase 3 テスト

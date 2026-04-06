# 問いの自動解決と知識変換機能 仕様・実装抜粋

本ドキュメントは `NEXUS_ARK_SPECIFICATION.md` の「9.4. 睡眠時処理」における以下機能の実装を抜粋：

- **問いの自動解決**: 会話で解決された問いを自動的にマーク
- **知識の変換**: 解決した問いをFACT（事実）またはINSIGHT（洞察）に変換

---

## 1. 概要

睡眠時処理（`dreaming_manager.py`）において、以下の処理が実行される：

1. 直近の会話を分析し、未解決の問いが解決されたか判定
2. 解決済みの問いをFACT/INSIGHTに分類して記憶に変換
3. 古い解決済み問いをクリーンアップ

---

## 2. 主要実装ファイル

| ファイル | 機能 | 関数 |
|---------|------|------|
| `motivation_manager.py` | 問い自動解決判定 | `auto_resolve_questions()` |
| `dreaming_manager.py` | 知識変換処理 | `_convert_resolved_questions_to_memory()` |
| `entity_memory_manager.py` | エンティティ記憶保存（FACT） | `create_or_update_entry()` |

---

## 3. 問いの自動解決 (`motivation_manager.py:794-872`)

### 3.1 関数定義

```python
def auto_resolve_questions(self, recent_conversation: str, api_key: str) -> List[str]:
    """
    対話内容から解決済みの問いを自動判定し、マークする。
    
    Args:
        recent_conversation: 直近の会話テキスト
        api_key: LLM呼び出し用のAPIキー
    
    Returns:
        解決されたと判定された問いのトピックリスト
    """
```

### 3.2 判定プロンプト

```
あなたはAIの記憶管理アシスタントです。
以下の「未解決の問い」のうち、「直近の会話」で回答・解決・言及された可能性のあるものを判定してください。

【判定ルール】
- その問いのトピックについて、会話で明確に話題になった場合は「解決」とみなす
- 部分的に触れられた場合も「解決」とみなす（再度聞く必要がないため）
- 全く触れられていない場合は「未解決」のまま

【出力形式】
解決した問いの番号をカンマ区切りで出力してください。
例: 1,3
何も解決していない場合は NONE と出力してください。
```

---

## 4. 知識の変換 (`dreaming_manager.py:633-732`)

### 4.1 関数定義

```python
def _convert_resolved_questions_to_memory(self, mm, recent_context: str, effective_settings: dict) -> int:
    """
    解決済みの質問を記憶（エンティティ記憶 or 夢日記）に変換する。
    
    Returns:
        変換した質問の数
    """
```

### 4.2 分類ルール

| 分類 | 説明 | 保存先 |
|------|------|--------|
| **FACT** | 人物・事物の属性、具体的な情報 | エンティティ記憶 (`memory/entities/*.md`) |
| **INSIGHT** | 関係性、感情的な気づき、行動パターン | 夢日記 (`private/insights.json`) |
| **SKIP** | 保存価値がない（曖昧すぎる等） | なし |

### 4.3 分類プロンプト

```
以下の「問い」と「回答」のペアから、記憶として保存すべき情報を抽出してください。

【分類ルール】
- FACT: 人物・事物の属性、具体的な情報（例：「田中さんは猫を飼っている」）
- INSIGHT: 関係性、感情的な気づき、行動パターン（例：「田中さんが創作を語る時、目が輝く」）
- SKIP: 保存する価値がない（曖昧すぎる、一時的すぎる等）

【出力形式】JSON
{
  "type": "FACT" | "INSIGHT" | "SKIP",
  "entity_name": "（FACTの場合、関連するエンティティ名）",
  "content": "（保存すべき内容）",
  "strategy": "（INSIGHTの場合、今後の対話にどう活かすか）",
  "reason": "（SKIPの場合のみ、理由）"
}
```

---

## 5. エンティティ記憶保存 (`entity_memory_manager.py:29-80`)

### 5.1 保存関数

```python
def create_or_update_entry(self, entity_name: str, content: str, 
                           append: bool = False, consolidate: bool = False, 
                           api_key: str = None) -> str:
    """
    Creates or updates an entity memory file.
    - append: Trueの場合、末尾に追記
    - consolidate: Trueの場合、LLMで統合・要約
    """
```

### 5.2 保存場所

```
{room_dir}/memory/entities/{entity_name}.md
```

---

## 6. 睡眠時処理での呼び出し順序 (`dreaming_manager.py:528-570`)

```python
# 1. 未解決の問いの自動解決判定
resolved = mm.auto_resolve_questions(recent_context, self.api_key)

# 2. 解決済み質問の記憶変換（Phase B）
converted_count = self._convert_resolved_questions_to_memory(mm, recent_context, effective_settings)

# 3. 解決済み質問のクリーンアップ
cleaned_count = mm.cleanup_resolved_questions(days_threshold=7)
decayed_count = mm.decay_old_questions(days_threshold=14)
```

---

## 7. データフロー

```
未解決の問い (open_questions.json)
    ↓ auto_resolve_questions()
解決済みとしてマーク (resolved_at 追加)
    ↓ _convert_resolved_questions_to_memory()
FACT → エンティティ記憶 (memory/entities/*.md)
INSIGHT → 夢日記 (private/insights.json)
    ↓ cleanup_resolved_questions()
古い解決済み問いを削除
```
# tools/knowledge_tools.py

import os
from pathlib import Path
from langchain_core.tools import tool
import traceback
import shutil
import tempfile
# 循環参照を避けるため、必要なモジュールは関数内でインポートする
import constants
import config_manager

# rag_manager は削除候補 - 直接 import せず関数内で条件付き import

@tool
def search_knowledge_base(query: str, room_name: str, api_key: str = None) -> str:
    """
    AI自身の長期的な知識ベース（Knowledge Base）に保存されている、外部から与えられたドキュメント（マニュアル、設定資料など）の内容について、自然言語で検索する。
    AI自身の記憶や過去の会話ではなく、普遍的な事実や情報を調べる場合に使用する。
    query: 検索したい内容を記述した、自然言語の質問文（例：「Nexus Arkの基本的な使い方は？」）。
    """
    
    # 1. 前提条件のチェック
    if not room_name:
        return "【エラー】検索対象のルームが指定されていません。"
    if not query:
        return "【エラー】検索クエリが指定されていません。"

    # 2. APIキーの準備
    if not api_key:
        api_key_name = config_manager.initial_api_key_name_global
        api_key = config_manager.GEMINI_API_KEYS.get(api_key_name)
    
    if not api_key or api_key.startswith("YOUR_API_KEY"):
        return f"【エラー】知識ベースの検索に必要なAPIキーが無効です。"
        
    # memx 経路を優先試行（rag_manager 削除済み）
    try:
        from tools.memx_tools import memx_search

        search_result = memx_search.invoke({
            "query": query,
            "room_name": room_name,
            "store": "knowledge",
            "top_k": 4
        })
        if search_result and "error" not in str(search_result).lower():
            return search_result

        # memx で結果が空の場合は空結果を返す
        return f"【検索結果】知識ベースから「{query}」に関連する情報は見つかりませんでした。"

    except Exception as memx_e:
        print(f"  - memx_search error: {memx_e}")
        traceback.print_exc()
        return f"【エラー】知識ベースの検索中にエラーが発生しました: {memx_e}"
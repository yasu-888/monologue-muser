"""環境変数の読み取り口。

値はモジュール定数ではなく呼び出し時に os.environ から読む。import 時に固定すると
テストで monkeypatch.setenv した値が効かず、未設定時のエラーも検証できないため。
"""

import os


def collection_name() -> str:
    return os.environ.get("COLLECTION_NAME", "firestore_collection_name")


def gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "gemini_api_key")


def gemini_model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def notion_api_key() -> str:
    return os.environ.get("NOTION_API_KEY", "your_notion_api_key")


def notion_database_id() -> str:
    return os.environ.get("NOTION_DATABASE_ID", "your_notion_database_id")

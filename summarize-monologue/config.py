"""環境変数の読み取り口。

値はモジュール定数ではなく呼び出し時に os.environ から読む。import 時に固定すると
テストで monkeypatch.setenv した値が効かず、未設定時のエラーも検証できないため。
"""

import os

_REQUIRED_NAMES = ("COLLECTION_NAME", "GEMINI_API_KEY", "NOTION_API_KEY", "NOTION_DATABASE_ID")


class MissingEnvError(RuntimeError):
    """必須の環境変数が未設定、または空文字のときに投げる。"""


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise MissingEnvError(f"必須の環境変数 {name} が未設定です")
    return value


def require_all() -> None:
    # 各関数の中で投げると firestore / notion / gemini の広い except に飲まれ、
    # 「処理済みとしてスキップ」などに化けて気づけない。処理の入口でまとめて検証する。
    missing = [name for name in _REQUIRED_NAMES if not os.environ.get(name)]
    if missing:
        raise MissingEnvError("必須の環境変数が未設定です: " + ", ".join(missing))


def collection_name() -> str:
    return _required("COLLECTION_NAME")


def gemini_api_key() -> str:
    return _required("GEMINI_API_KEY")


def gemini_model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def notion_api_key() -> str:
    return _required("NOTION_API_KEY")


def notion_database_id() -> str:
    return _required("NOTION_DATABASE_ID")

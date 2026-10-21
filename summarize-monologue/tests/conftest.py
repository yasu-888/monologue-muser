import pytest

# 必須 env は全テストで設定済みを前提にする。未設定を検証するテストだけ delenv で外す。
# プロセス環境を汚さないよう monkeypatch で設定する。
_REQUIRED_ENV = {
    "COLLECTION_NAME": "test-collection",
    "GEMINI_API_KEY": "test-gemini-key",
    "NOTION_API_KEY": "test-notion-key",
    "NOTION_DATABASE_ID": "test-database-id",
}


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    for name, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)

import config
import pytest

# 必須 env の関数と変数名の対応。未設定・空文字の扱いは全てこの表で検証する。
_REQUIRED = [
    (config.collection_name, "COLLECTION_NAME"),
    (config.gemini_api_key, "GEMINI_API_KEY"),
    (config.notion_api_key, "NOTION_API_KEY"),
    (config.notion_database_id, "NOTION_DATABASE_ID"),
]


@pytest.mark.parametrize(("getter", "name"), _REQUIRED)
def test_必須変数が未設定なら例外になり変数名を含む(monkeypatch, getter, name):
    monkeypatch.delenv(name, raising=False)
    with pytest.raises(config.MissingEnvError, match=name):
        getter()


@pytest.mark.parametrize(("getter", "name"), _REQUIRED)
def test_必須変数が空文字なら未設定として例外になる(monkeypatch, getter, name):
    monkeypatch.setenv(name, "")
    with pytest.raises(config.MissingEnvError, match=name):
        getter()


@pytest.mark.parametrize(("getter", "name"), _REQUIRED)
def test_必須変数が設定済みならその値を返す(monkeypatch, getter, name):
    monkeypatch.setenv(name, "実値")
    assert getter() == "実値"


def test_GEMINI_MODELは未設定なら既定値のgemini_2_5_flashを返す(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert config.gemini_model() == "gemini-2.5-flash"


def test_require_allは欠けた変数名をすべて含めて例外を投げる(monkeypatch):
    for _, name in _REQUIRED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("COLLECTION_NAME", "c")
    with pytest.raises(config.MissingEnvError) as excinfo:
        config.require_all()
    message = str(excinfo.value)
    assert "GEMINI_API_KEY" in message
    assert "NOTION_API_KEY" in message
    assert "NOTION_DATABASE_ID" in message
    assert "COLLECTION_NAME" not in message


def test_require_allは必須変数がすべて揃っていれば何もしない(monkeypatch):
    for _, name in _REQUIRED:
        monkeypatch.setenv(name, "x")
    config.require_all()

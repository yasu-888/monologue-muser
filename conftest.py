"""pytest 実行ガード。

upload-monologue と summarize-monologue はどちらも main.py を持つため、
1 つの pytest プロセスで両方を集めると sys.modules 上で `main` が衝突し、
後から集めた側のテストが誤ったモジュールを参照して失敗する。
謎の失敗を防ぐため、両方が同時に集められたら明示的にエラーにする。

実行方法:
    uv run pytest upload-monologue
    uv run pytest summarize-monologue
"""

import pytest

_SERVICE_DIRS = ("upload-monologue", "summarize-monologue")


def pytest_collection_modifyitems(items):
    collected = {d for d in _SERVICE_DIRS for item in items if d in str(item.fspath)}
    if len(collected) > 1:
        raise pytest.UsageError(
            "両サービスの main.py がモジュール名衝突するため、"
            "テストはサービス単位で実行してください: "
            "`uv run pytest upload-monologue` / `uv run pytest summarize-monologue`"
        )

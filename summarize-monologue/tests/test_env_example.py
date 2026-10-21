""".env.example のキー集合がコードの読む env 名と一致することを確かめる。

キー一覧をテストに書かない。サービス直下の .py（tests/ と conftest.py を除く）から
環境変数名を拾い、.env.example のキーと比べる。
"""

import re
from pathlib import Path

_SERVICE_DIR = Path(__file__).resolve().parents[1]

# os.environ.get("X") / os.environ["X"] と、必須変数のヘルパー _required("X") を拾う。
_READ_PATTERNS = [
    re.compile(r"""os\.environ\.get\(\s*["']([A-Z][A-Z0-9_]*)["']"""),
    re.compile(r"""os\.environ\[\s*["']([A-Z][A-Z0-9_]*)["']\s*\]"""),
    re.compile(r"""_required\(\s*["']([A-Z][A-Z0-9_]*)["']"""),
]


def _names_read_by_code() -> set[str]:
    names: set[str] = set()
    for path in _SERVICE_DIR.glob("*.py"):
        if path.name == "conftest.py":
            continue
        source = path.read_text(encoding="utf-8")
        for pattern in _READ_PATTERNS:
            names.update(pattern.findall(source))
    return names


def _keys_in_env_example() -> set[str]:
    keys: set[str] = set()
    for line in (_SERVICE_DIR / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        # 区分見出しのコメントと空行は値を持たないので無視する。
        if not line or line.startswith("#"):
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def test_env_exampleのキー集合がコードの読む環境変数名と一致する():
    assert _keys_in_env_example() == _names_read_by_code()

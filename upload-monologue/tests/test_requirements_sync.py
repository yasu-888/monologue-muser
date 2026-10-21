"""requirements.txt が uv の lock から生成した結果と一致することを確かめる。

本番 (buildpacks) は requirements.txt を読むが、テストは uv.lock の版で動く。
両者が食い違うとテストが検証している版と本番の版が別物になるため、
生成コマンドを再実行して差が無いことをここで固定する。
再生成は pyproject.toml のヘッダに書いた uv export を実行する。
"""

import shutil
import subprocess
from pathlib import Path

_SERVICE = "upload-monologue"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_REQUIREMENTS = _REPO_ROOT / _SERVICE / "requirements.txt"


def test_requirements_txt_は_uv_export_の結果と一致する():
    # uv が無い環境では skip せず失敗させる。skip だと CI で同期が検査されないまま緑になるため。
    assert shutil.which("uv") is not None, "uv が PATH に無い（CI でも uv を入れること）"

    result = subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--only-group",
            _SERVICE,
            "--no-hashes",
            "--no-emit-project",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert _REQUIREMENTS.read_text(encoding="utf-8") == result.stdout

# AGENTS

- 仕様と構成は `README.md` を正とする。
- `private/` がある clone が正本（作業場）。public の repo はそこから `private/bin/publish.sh` で書き出すだけなので、`private/` が無い clone では編集しない。
- テストはサービス単位で実行する（両サービスの `main.py` がモジュール名で衝突するため）: `uv run pytest upload-monologue` / `uv run pytest summarize-monologue`。各 1 秒未満。
- 本番依存の正本は `pyproject.toml` のサービス別 group と `uv.lock`。各 `requirements.txt` は生成物なので手で編集せず、`pyproject.toml` 冒頭のコマンドで再生成する。
- ruff・pytest は CI（`.github/workflows/ci.yml`）が push / PR で回す。

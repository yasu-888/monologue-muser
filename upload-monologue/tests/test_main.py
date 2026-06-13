"""upload-monologue/main.py の振る舞いテスト。

GCP 認証 (google.auth.default, storage.Client, blob.generate_signed_url) は
テスト内で mock する。functions-framework HTTP 関数は Flask test request context で駆動する。
"""

import json
from unittest.mock import MagicMock, patch

from flask import Flask  # third-party
from main import (  # local
    _ext_to_content_type,
    _sanitize_extension,
    _sanitize_title,
    generate_signed_url,
)

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

_FAKE_URL = "https://storage.googleapis.com/fake-bucket/fake-object?X-Goog-Signature=xxx"


def _make_app() -> Flask:
    return Flask(__name__)


def _call(app: Flask, body: dict | None, method: str = "POST") -> tuple:
    """generate_signed_url を Flask test request context で呼び出す。"""
    with app.test_request_context(
        "/",
        method=method,
        data=json.dumps(body),
        content_type="application/json",
    ):
        from flask import request as flask_request

        return generate_signed_url(flask_request)


def _patch_gcp(signed_url: str = _FAKE_URL):
    """GCP 依存を一括 mock するコンテキストマネージャーを返す。"""
    mock_credentials = MagicMock()
    mock_credentials.service_account_email = "svc@project.iam.gserviceaccount.com"
    mock_credentials.token = "fake-token"

    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = signed_url

    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    patches = [
        patch("main.google.auth.default", return_value=(mock_credentials, "project")),
        patch("main.storage.Client", return_value=mock_client),
    ]
    return patches, mock_blob


# ---------------------------------------------------------------------------
# _ext_to_content_type: 拡張子 → MIME タイプ
# ---------------------------------------------------------------------------


class TestExtToContentType:
    def test_aiff_returns_audio_aiff(self):
        assert _ext_to_content_type("aiff") == "audio/aiff"

    def test_aif_returns_audio_aiff(self):
        assert _ext_to_content_type("aif") == "audio/aiff"

    def test_m4a_returns_audio_mp4(self):
        assert _ext_to_content_type("m4a") == "audio/mp4"

    def test_mp3_returns_audio_mpeg(self):
        assert _ext_to_content_type("mp3") == "audio/mpeg"

    def test_wav_returns_audio_wav(self):
        assert _ext_to_content_type("wav") == "audio/wav"

    def test_unknown_extension_returns_octet_stream(self):
        # 未知の拡張子は汎用バイナリにフォールバック。
        # PUT 時の Content-Type 一致はクライアント側の責務。
        assert _ext_to_content_type("xyz") == "application/octet-stream"

    def test_uppercase_extension_is_normalized(self):
        assert _ext_to_content_type("AIFF") == "audio/aiff"


# ---------------------------------------------------------------------------
# _sanitize_title: タイトルのサニタイズ
# ---------------------------------------------------------------------------


class TestSanitizeTitle:
    def test_slash_replaced_with_hyphen(self):
        # '/' はオブジェクト名にそのまま入ると疑似ディレクトリになりパスが崩れる
        assert _sanitize_title("a/b") == "a-b"

    def test_backslash_replaced_with_hyphen(self):
        assert _sanitize_title("a\\b") == "a-b"

    def test_nul_byte_removed(self):
        assert _sanitize_title("ab\x00cd") == "abcd"

    def test_leading_trailing_whitespace_stripped(self):
        assert _sanitize_title("  hello  ") == "hello"

    def test_normal_title_unchanged(self):
        assert _sanitize_title("散歩日記") == "散歩日記"

    def test_multiple_slashes(self):
        assert _sanitize_title("a/b/c") == "a-b-c"


# ---------------------------------------------------------------------------
# _sanitize_extension: 拡張子のサニタイズ
# ---------------------------------------------------------------------------


class TestSanitizeExtension:
    def test_normal_extension_passes_through(self):
        assert _sanitize_extension("m4a") == "m4a"

    def test_uppercase_is_lowercased(self):
        assert _sanitize_extension("AIFF") == "aiff"

    def test_path_separator_is_removed(self):
        # 拡張子もオブジェクト名の一部なので '/' が入るとパスが崩れる
        assert _sanitize_extension("a/if") == "aif"

    def test_non_string_falls_back_to_aiff(self):
        assert _sanitize_extension(123) == "aiff"

    def test_empty_after_cleanup_falls_back_to_aiff(self):
        assert _sanitize_extension("../") == "aiff"


# ---------------------------------------------------------------------------
# generate_signed_url: HTTP 関数の振る舞い
# ---------------------------------------------------------------------------


class TestGenerateSignedUrl:
    def setup_method(self):
        self.app = _make_app()

    # --- CORS preflight ---

    def test_options_returns_204_with_cors_headers(self):
        with self.app.test_request_context("/", method="OPTIONS"):
            from flask import request as flask_request

            result = generate_signed_url(flask_request)
        body, status, headers = result
        assert status == 204
        assert headers["Access-Control-Allow-Origin"] == "*"
        assert "POST" in headers["Access-Control-Allow-Methods"]

    # --- バリデーション ---

    def test_missing_title_returns_400(self):
        result = _call(self.app, {"file_extension": "aiff"})
        _, status, _ = result
        assert status == 400

    def test_empty_body_returns_400(self):
        result = _call(self.app, None)
        _, status, _ = result
        assert status == 400

    def test_empty_string_title_returns_400(self):
        result = _call(self.app, {"title": ""})
        _, status, _ = result
        assert status == 400

    def test_whitespace_only_title_returns_400(self):
        result = _call(self.app, {"title": "   "})
        _, status, _ = result
        assert status == 400

    # --- 正常系: レスポンス構造 ---

    def test_success_returns_200_with_signed_url_and_filename(self):
        patches, _ = _patch_gcp()
        with patches[0], patches[1]:
            result = _call(self.app, {"title": "朝の散歩", "file_extension": "m4a"})
        response_obj, status, headers = result
        assert status == 200
        data = json.loads(response_obj.get_data(as_text=True))
        assert "signed_url" in data
        assert "filename" in data
        assert headers["Access-Control-Allow-Origin"] == "*"

    def test_filename_format_is_timestamp_uuid8_title_ext(self):
        """filename が {timestamp}_{uuid8}_{title}.{ext} 形式であることを固定する。

        summarize-monologue が '_' で split し第3要素以降をタイトルとして使うため形式変更禁止。
        """
        patches, _ = _patch_gcp()
        with patches[0], patches[1]:
            result = _call(self.app, {"title": "夕方の記録", "file_extension": "aiff"})
        data = json.loads(result[0].get_data(as_text=True))
        filename = data["filename"]
        parts = filename.split("_")
        assert len(parts) >= 3, f"filename parts < 3: {filename}"
        timestamp_part, uuid8_part = parts[0], parts[1]
        assert len(timestamp_part) == 14 and timestamp_part.isdigit()
        assert len(uuid8_part) == 8
        assert filename.endswith(".aiff")

    def test_content_type_matches_extension_m4a(self):
        """m4a を渡したとき署名付き URL の content_type が audio/mp4 になること。

        署名対象に content_type が含まれるため、PUT 時の Content-Type と不一致だと 403 になる。
        """
        patches, mock_blob = _patch_gcp()
        with patches[0], patches[1]:
            _call(self.app, {"title": "テスト", "file_extension": "m4a"})
        call_kwargs = mock_blob.generate_signed_url.call_args.kwargs
        assert call_kwargs["content_type"] == "audio/mp4"

    def test_content_type_matches_extension_aiff(self):
        patches, mock_blob = _patch_gcp()
        with patches[0], patches[1]:
            _call(self.app, {"title": "テスト", "file_extension": "aiff"})
        call_kwargs = mock_blob.generate_signed_url.call_args.kwargs
        assert call_kwargs["content_type"] == "audio/aiff"

    def test_default_extension_is_aiff(self):
        """file_extension 省略時は aiff がデフォルト。"""
        patches, mock_blob = _patch_gcp()
        with patches[0], patches[1]:
            _call(self.app, {"title": "テスト"})
        call_kwargs = mock_blob.generate_signed_url.call_args.kwargs
        assert call_kwargs["content_type"] == "audio/aiff"

    def test_signed_url_expiration_is_15_minutes(self):
        """署名付き URL の有効期限が 15 分であることを固定する。"""
        import datetime

        patches, mock_blob = _patch_gcp()
        with patches[0], patches[1]:
            _call(self.app, {"title": "テスト", "file_extension": "aiff"})
        call_kwargs = mock_blob.generate_signed_url.call_args.kwargs
        assert call_kwargs["expiration"] == datetime.timedelta(minutes=15)

    def test_signed_url_method_is_put(self):
        patches, mock_blob = _patch_gcp()
        with patches[0], patches[1]:
            _call(self.app, {"title": "テスト", "file_extension": "aiff"})
        call_kwargs = mock_blob.generate_signed_url.call_args.kwargs
        assert call_kwargs["method"] == "PUT"

    def test_title_with_slash_is_sanitized_in_filename(self):
        """タイトルに '/' が含まれる場合、ファイル名が疑似ディレクトリ構造にならないこと。"""
        patches, _ = _patch_gcp()
        with patches[0], patches[1]:
            result = _call(self.app, {"title": "a/b/c", "file_extension": "aiff"})
        data = json.loads(result[0].get_data(as_text=True))
        assert "/" not in data["filename"].split("_", 2)[2]

    def test_unknown_extension_uses_octet_stream(self):
        """未知の拡張子は application/octet-stream にフォールバックする。"""
        patches, mock_blob = _patch_gcp()
        with patches[0], patches[1]:
            _call(self.app, {"title": "テスト", "file_extension": "xyz"})
        call_kwargs = mock_blob.generate_signed_url.call_args.kwargs
        assert call_kwargs["content_type"] == "application/octet-stream"

    def test_gcp_error_returns_500(self):
        with patch("main.google.auth.default", side_effect=Exception("auth failed")):
            result = _call(self.app, {"title": "テスト", "file_extension": "aiff"})
        _, status, _ = result
        assert status == 500

import datetime
import os
import uuid

import functions_framework
import google.auth
import google.auth.transport.requests
from flask import jsonify
from google.cloud import storage

# デプロイ先 GCS バケット名。環境変数で注入する
BUCKET_NAME = os.environ.get("BUCKET_NAME", "gcs_bucket_name")

# 拡張子 → MIME タイプの対応表。
# GCS 署名付き PUT URL は content_type を署名対象に含めるため、
# クライアントが PUT 時に送る Content-Type と一致しないと 403 になる。
# (外部仕様: https://cloud.google.com/storage/docs/resumable-uploads#initiate-upload)
_EXT_TO_MIME: dict[str, str] = {
    "aiff": "audio/aiff",
    "aif": "audio/aiff",
    "m4a": "audio/mp4",
    "mp3": "audio/mpeg",
    "mp4": "audio/mp4",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
    "webm": "audio/webm",
}
_FALLBACK_MIME = "application/octet-stream"


def _ext_to_content_type(extension: str) -> str:
    """拡張子から MIME タイプを返す。未知の拡張子は汎用バイナリにフォールバック。"""
    return _EXT_TO_MIME.get(extension.lower(), _FALLBACK_MIME)


def _sanitize_title(title: str) -> str:
    """GCS オブジェクト名を壊す文字を置換・除去する。

    '/' は GCS オブジェクト名の疑似ディレクトリ区切りとして機能するため、
    タイトルに含まれるとオブジェクト名がパス構造を持ってしまう。
    '_' はファイル名の区切り文字だが、summarize 側が第3要素以降を連結して
    タイトルを復元するため、置換せず通してよい。
    """
    sanitized = title.replace("/", "-").replace("\\", "-").replace("\0", "")
    return sanitized.strip()


def _sanitize_extension(extension) -> str:
    """拡張子は英数字のみ許可する。不正・空なら従来デフォルトの aiff に落とす。

    拡張子もオブジェクト名の一部になるため、'/' などを含むと title と同様に
    オブジェクト名が崩れる。
    """
    if not isinstance(extension, str):
        return "aiff"
    cleaned = "".join(ch for ch in extension if ch.isalnum())
    return cleaned.lower() or "aiff"


@functions_framework.http
def generate_signed_url(request):
    """GCS の署名付き PUT URL を返す Cloud Run function。

    iOS ショートカットから呼ばれる。
    ファイル名形式: {timestamp}_{uuid8}_{title}.{ext}
    (summarize-monologue が第3要素以降をタイトルとして使うため形式変更禁止)
    """
    # preflight CORS
    if request.method == "OPTIONS":
        return (
            "",
            204,
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "3600",
            },
        )

    headers = {"Access-Control-Allow-Origin": "*"}

    try:
        request_data = request.get_json()

        if not request_data or "title" not in request_data:
            return jsonify({"error": "タイトルが指定されていません"}), 400, headers

        raw_title = request_data["title"]
        if not isinstance(raw_title, str) or not raw_title.strip():
            return jsonify({"error": "タイトルが空です"}), 400, headers

        title = _sanitize_title(raw_title)
        file_extension = _sanitize_extension(request_data.get("file_extension", "aiff"))
        content_type = _ext_to_content_type(file_extension)

        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        file_id = str(uuid.uuid4())[:8]
        filename = f"{timestamp}_{file_id}_{title}.{file_extension}"

        credentials, _ = google.auth.default()
        credentials.refresh(google.auth.transport.requests.Request())
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)

        # 署名付き URL の有効期限は 15 分
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=content_type,
            service_account_email=credentials.service_account_email,
            access_token=credentials.token,
        )

        return jsonify({"signed_url": url, "filename": filename}), 200, headers

    except Exception as e:
        return jsonify({"error": str(e)}), 500, headers

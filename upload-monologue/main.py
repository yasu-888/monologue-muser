import functions_framework
from flask import jsonify, request
from google.cloud import storage
import google.auth
import google.auth.transport.requests
import datetime
import uuid
import os
import json

# 環境変数からバケット名を取得
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'gcs_bucket_name')

@functions_framework.http
def generate_signed_url(request):
    """GCSの署名付きURLをHTTPリクエストから生成する。
    リクエストから'title'パラメータを取得し、ファイル名に含める。

    Args:
        request (flask.Request): HTTPリクエストオブジェクト。

    Returns:
        flask.Response: 署名付きURLを含むJSONレスポンス。
    """
    # CORSヘッダーを設定
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)
    
    headers = {
        'Access-Control-Allow-Origin': '*'
    }

    try:
        request_data = request.get_json()

        if not request_data or 'title' not in request_data:
            return jsonify({'error': 'タイトルが指定されていません'}), 400, headers

        title = request_data['title']
        file_extension = request_data.get('file_extension', 'aiff')  # デフォルトはaiffとする

        # ファイル名を生成（タイトルとUUIDを含む）
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        file_id = str(uuid.uuid4())[:8]
        filename = f"{timestamp}_{file_id}_{title}.{file_extension}"

        # Cloud Storageクライアントを初期化
        credentials, _ = google.auth.default()
        credentials.refresh(google.auth.transport.requests.Request())
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)

        # 署名付きURLを生成（15分間有効）
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type="audio/aiff",  # メディアタイプを設定する
            service_account_email=credentials.service_account_email,
            access_token=credentials.token,
        )

        response = {
            'signed_url': url,
            'filename': filename
        }

        return jsonify(response), 200, headers

    except Exception as e:
        return jsonify({'error': str(e)}), 500, headers
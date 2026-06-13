from google.cloud import storage

# storage.Client は import 時ではなく初回利用時に生成する。
# 認証なしのテスト環境で import できること、Cloud Run コールドスタートでの遅延初期化が目的。
_storage_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


def download_file_from_gcs(bucket_name, file_name, local_file_path):
    """GCS からファイルをダウンロードする。成功で True。"""
    try:
        bucket = _get_client().bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.download_to_filename(local_file_path)
        print(f"GCSからファイル '{file_name}' を '{local_file_path}' にダウンロードしました。")
        return True
    except Exception as e:
        print(f"GCSからのファイルダウンロード中にエラーが発生しました: {e}")
        return False


def delete_file_from_gcs(bucket_name, file_name):
    """GCS からファイルを削除する。成功で True。"""
    try:
        bucket = _get_client().bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.delete()
        print(f"GCSバケット '{bucket_name}' からファイル '{file_name}' を削除しました。")
        return True
    except Exception as e:
        print(f"GCSからのファイル削除中にエラーが発生しました: {e}")
        return False

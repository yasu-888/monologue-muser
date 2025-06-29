from google.cloud import storage
import os

storage_client = storage.Client()

def download_file_from_gcs(bucket_name, file_name, local_file_path):
    """
    GCSからファイルをダウンロードします。
    
    Args:
        bucket_name (str): GCSバケット名
        file_name (str): ファイル名
        local_file_path (str): ダウンロード先のローカルパス
        
    Returns:
        bool: ダウンロードが成功した場合はTrue、失敗した場合はFalse
    """
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.download_to_filename(local_file_path)
        print(f"GCSからファイル '{file_name}' を '{local_file_path}' にダウンロードしました。")
        return True
    except Exception as e:
        print(f"GCSからのファイルダウンロード中にエラーが発生しました: {e}")
        return False

def delete_file_from_gcs(bucket_name, file_name):
    """
    GCSからファイルを削除します。
    
    Args:
        bucket_name (str): GCSバケット名
        file_name (str): ファイル名
        
    Returns:
        bool: 削除が成功した場合はTrue、失敗した場合はFalse
    """
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.delete()
        print(f"GCSバケット '{bucket_name}' からファイル '{file_name}' を削除しました。")
        return True
    except Exception as e:
        print(f"GCSからのファイル削除中にエラーが発生しました: {e}")
        return False
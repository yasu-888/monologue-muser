import functions_framework
import os
import json
from cloud_storage_service import download_file_from_gcs, delete_file_from_gcs
from gemini_service import transcribe_and_summarize
from notion_service import send_to_notion
from firestore_service import generate_event_id, try_start_processing, mark_processing_completed

BUCKET_NAME = os.environ.get('BUCKET_NAME', 'gcs_bucket_name')

@functions_framework.cloud_event
def summarize_monologue(cloud_event):
    """
    GCSへのファイルアップロードをトリガーに音声ファイルを処理する関数
    
    Args:
        cloud_event: CloudEventのオブジェクト
    """
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]
    
    # 重複実行防止: Firestoreトランザクションを使用してアトミックに処理開始をマーク
    event_id = generate_event_id(bucket_name, file_name)
    print(f"生成されたイベントID: {event_id} (バケット: {bucket_name}, ファイル: {file_name})")
    
    # トランザクション内で処理開始を試行（重複実行防止）
    if not try_start_processing(event_id, bucket_name, file_name):
        print(f"イベント {event_id} は既に処理済みまたは処理中です処理をスキップします")
        return "Event already processed or in progress"
    
    print(f"新規処理開始: ファイル名={file_name}, バケット名={bucket_name}, イベントID={event_id}")

    local_file_path = f"/tmp/{file_name}"
    
    try:
        # 1. GCSから音声ファイルをダウンロード
        if not download_file_from_gcs(bucket_name, file_name, local_file_path):
            return "ファイルのダウンロード中にエラーが発生しました"
        
        # 2. Gemini APIで文字起こしと要約を実行
        result_json = transcribe_and_summarize(local_file_path)
        markdown_content = result_json["markdown"]
        next_action_list = result_json.get("nextActions", [])
        next_action_markdown = "### NextActions\n" + "\n".join([f"- {action}" for action in next_action_list]) if next_action_list else ""
        tags = result_json["tags"]

        # 3. Notionに結果を送信
        if not send_to_notion(file_name, markdown_content, next_action_markdown, tags):
            return "Notionへの送信中にエラーが発生しました"
        
        # 4. GCSからファイルを削除
        delete_file_from_gcs(bucket_name, file_name)
        
        # 5. 一時ファイルの削除
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
        
        # 6. 処理完了をFirestoreに記録
        if not mark_processing_completed(event_id, bucket_name, file_name):
            print(f"警告: イベント {event_id} の処理完了記録に失敗しました")
        else:
            print(f"処理完了記録成功: イベントID={event_id}")
        
        return "処理が正常に完了しました"
        
    except Exception as e:
        print(f"音声処理中にエラーが発生しました: {e}")
        # エラーが発生した場合でも一時ファイルを削除
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
        return f"Error: {str(e)}"
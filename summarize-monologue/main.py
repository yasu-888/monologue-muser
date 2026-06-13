import os

import functions_framework
from cloud_storage_service import delete_file_from_gcs, download_file_from_gcs
from firestore_service import (
    generate_event_id,
    mark_processing_completed,
    mark_processing_failed,
    try_start_processing,
)
from gemini_service import transcribe_and_summarize
from notion_service import send_to_notion

BUCKET_NAME = os.environ.get('BUCKET_NAME', 'gcs_bucket_name')


def _local_tmp_path(file_name: str) -> str:
    """GCS オブジェクト名から /tmp 内の安全なローカルパスを作る。

    GCS のオブジェクト名にはスラッシュが合法に含まれるため、そのまま /tmp に連結すると
    存在しないサブディレクトリへの書き込みになり失敗する。basename 化して回避する。
    """
    return f"/tmp/{os.path.basename(file_name)}"


@functions_framework.cloud_event
def summarize_monologue(cloud_event):
    """GCS へのファイルアップロードをトリガーに音声ファイルを処理する関数。"""
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    # 重複実行防止: Firestore トランザクションでアトミックに処理開始をマークする。
    event_id = generate_event_id(bucket_name, file_name)
    print(f"生成されたイベントID: {event_id} (バケット: {bucket_name}, ファイル: {file_name})")

    if not try_start_processing(event_id, bucket_name, file_name):
        print(f"イベント {event_id} は既に処理済みまたは処理中です処理をスキップします")
        return "Event already processed or in progress"

    print(f"新規処理開始: ファイル名={file_name}, バケット名={bucket_name}, イベントID={event_id}")

    local_file_path = _local_tmp_path(file_name)

    try:
        # 1. GCS から音声ファイルをダウンロード
        if not download_file_from_gcs(bucket_name, file_name, local_file_path):
            # 失敗時は重複防止ドキュメントを消し、再配信/再アップロードでの再処理を可能にする。
            mark_processing_failed(event_id, bucket_name, file_name)
            return "ファイルのダウンロード中にエラーが発生しました"

        # 2. Gemini API で文字起こしと要約を実行
        result_json = transcribe_and_summarize(local_file_path)
        markdown_content = result_json["markdown"]
        next_action_list = result_json["nextActions"]
        next_action_markdown = (
            "### NextActions\n" + "\n".join(f"- {action}" for action in next_action_list)
            if next_action_list
            else ""
        )
        tags = result_json["tags"]

        # 3. Notion に結果を送信
        if not send_to_notion(file_name, markdown_content, next_action_markdown, tags):
            mark_processing_failed(event_id, bucket_name, file_name)
            return "Notionへの送信中にエラーが発生しました"

        # 4. GCS からファイルを削除
        delete_file_from_gcs(bucket_name, file_name)

        # 5. 処理完了を Firestore に記録
        if not mark_processing_completed(event_id, bucket_name, file_name):
            print(f"警告: イベント {event_id} の処理完了記録に失敗しました")
        else:
            print(f"処理完了記録成功: イベントID={event_id}")

        return "処理が正常に完了しました"

    except Exception as e:
        print(f"音声処理中にエラーが発生しました: {e}")
        # 例外時も重複防止ドキュメントを消して再試行可能にする。
        mark_processing_failed(event_id, bucket_name, file_name)
        return f"Error: {str(e)}"

    finally:
        # 一時ファイル削除は成功・失敗いずれの経路でも必ず行う。
        if os.path.exists(local_file_path):
            os.remove(local_file_path)

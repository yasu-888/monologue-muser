import os
from google.cloud import firestore
import hashlib
from datetime import datetime, timedelta

db = firestore.Client()
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'firestore_collection_name')

def generate_event_id(bucket_name: str, file_name: str, event_time: str = None) -> str:
    """
    イベントの一意識別子を生成
    
    Args:
        bucket_name: GCSバケット名
        file_name: ファイル名
        event_time: イベント時刻（任意）
    
    Returns:
        str: 生成されたイベントID
    """
    content = f"{bucket_name}/{file_name}"
    if event_time:
        content += f"/{event_time}"
    
    return hashlib.md5(content.encode()).hexdigest()

@firestore.transactional
def _try_start_processing_transaction(transaction, doc_ref: firestore.DocumentReference, bucket_name: str, file_name: str) -> bool:
    """
    トランザクション内でアトミックに処理開始をマーク
    
    Args:
        transaction: Firestoreトランザクション
        doc_ref: ドキュメント参照
        bucket_name: GCSバケット名
        file_name: ファイル名
    
    Returns:
        bool: 処理開始に成功した場合True、既に処理済み/処理中の場合False
    """
    # トランザクション内でドキュメントの存在確認
    doc = doc_ref.get(transaction=transaction)
    
    if doc.exists:
        print(f"イベントは既に処理済みまたは処理中です: {doc_ref.id}")
        return False
    
    # 未処理の場合、処理開始ステータスで作成
    doc_data = {
        'bucket_name': bucket_name,
        'file_name': file_name,
        'started_at': datetime.utcnow(),
        'status': 'processing'
    }
    transaction.set(doc_ref, doc_data)
    print(f"処理開始をマーク: {doc_ref.id}")
    return True

def try_start_processing(event_id: str, bucket_name: str, file_name: str) -> bool:
    """
    イベント処理の開始を試行（重複実行防止）
    
    Args:
        event_id: イベントID
        bucket_name: GCSバケット名
        file_name: ファイル名
    
    Returns:
        bool: 処理開始に成功した場合True、重複実行の場合False
    """
    try:
        doc_ref = db.collection(COLLECTION_NAME).document(event_id)
        transaction = db.transaction()
        
        # トランザクション内でアトミックに処理開始をマーク
        return _try_start_processing_transaction(transaction, doc_ref, bucket_name, file_name)
        
    except Exception as e:
        print(f"処理開始試行エラー: {e}")
        print(f"コレクション名: {COLLECTION_NAME}, イベントID: {event_id}")
        return False

def mark_processing_completed(event_id: str, bucket_name: str, file_name: str) -> bool:
    """
    イベント処理の完了を記録し、TTL用の有効期限を設定します。
    
    Args:
        event_id: イベントID
        bucket_name: GCSバケット名
        file_name: ファイル名
    
    Returns:
        bool: 成功した場合True、失敗した場合False
    """
    try:
        doc_ref = db.collection(COLLECTION_NAME).document(event_id)

        # Pub/Subの最大メッセージ保持期間（デフォルト7日）を考慮し、少し余裕を持たせて10日後に設定
        # この期間を過ぎたドキュメントは重複実行防止の役目を終えたと判断できます。
        retention_days = 10
        completion_time = datetime.utcnow()
        expire_at_time = completion_time + timedelta(days=retention_days)

        # 部分更新で完了ステータスと有効期限を記録
        doc_ref.update({
            'completed_at': completion_time,
            'status': 'completed',
            'expire_at': expire_at_time  # TTL (Time-to-Live) ポリシー用のフィールド
        })
        print(f"処理完了を記録: コレクション='{COLLECTION_NAME}', ドキュメントID='{event_id}'")
        print(f"ドキュメントは {expire_at_time.isoformat()} ごろに自動削除されます。")
        return True
    except Exception as e:
        print(f"処理完了記録エラー: {e}")
        print(f"コレクション名: {COLLECTION_NAME}, イベントID: {event_id}")
        return False
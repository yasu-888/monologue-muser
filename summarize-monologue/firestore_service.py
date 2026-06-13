import hashlib
import os
from datetime import UTC, datetime, timedelta

from google.cloud import firestore

COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'firestore_collection_name')

# firestore.Client は import 時ではなく初回利用時に生成する。
# 認証なしのテスト環境で import できること、および Cloud Run のコールドスタートで
# 不要な初期化を遅延させることが目的。モジュールグローバルにキャッシュして使い回す。
_db: firestore.Client | None = None


def _get_db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def generate_event_id(bucket_name: str, file_name: str, event_time: str | None = None) -> str:
    content = f"{bucket_name}/{file_name}"
    if event_time:
        content += f"/{event_time}"

    return hashlib.md5(content.encode()).hexdigest()


@firestore.transactional
def _try_start_processing_transaction(
    transaction,
    doc_ref: firestore.DocumentReference,
    bucket_name: str,
    file_name: str,
) -> bool:
    """トランザクション内でアトミックに処理開始をマークし、重複実行を防ぐ。

    ドキュメントが既に存在すれば（処理中/処理済み）False を返す。
    """
    doc = doc_ref.get(transaction=transaction)

    if doc.exists:
        print(f"イベントは既に処理済みまたは処理中です: {doc_ref.id}")
        return False

    doc_data = {
        'bucket_name': bucket_name,
        'file_name': file_name,
        'started_at': datetime.now(UTC),
        'status': 'processing',
    }
    transaction.set(doc_ref, doc_data)
    print(f"処理開始をマーク: {doc_ref.id}")
    return True


def try_start_processing(event_id: str, bucket_name: str, file_name: str) -> bool:
    """イベント処理の開始を試行する。重複実行なら False。"""
    try:
        db = _get_db()
        doc_ref = db.collection(COLLECTION_NAME).document(event_id)
        transaction = db.transaction()

        return _try_start_processing_transaction(transaction, doc_ref, bucket_name, file_name)

    except Exception as e:
        print(f"処理開始試行エラー: {e}")
        print(f"コレクション名: {COLLECTION_NAME}, イベントID: {event_id}")
        return False


def mark_processing_completed(event_id: str, bucket_name: str, file_name: str) -> bool:
    """イベント処理の完了を記録し、TTL 用の有効期限を設定する。"""
    try:
        db = _get_db()
        doc_ref = db.collection(COLLECTION_NAME).document(event_id)

        # Pub/Sub の最大メッセージ保持期間（デフォルト7日）を考慮し、
        # 少し余裕を持たせて10日後に設定。
        # この期間を過ぎたドキュメントは重複実行防止の役目を終えたと判断できる。
        retention_days = 10
        completion_time = datetime.now(UTC)
        expire_at_time = completion_time + timedelta(days=retention_days)

        doc_ref.update({
            'completed_at': completion_time,
            'status': 'completed',
            'expire_at': expire_at_time,  # TTL (Time-to-Live) ポリシー用のフィールド
        })
        print(f"処理完了を記録: コレクション='{COLLECTION_NAME}', ドキュメントID='{event_id}'")
        print(f"ドキュメントは {expire_at_time.isoformat()} ごろに自動削除されます。")
        return True
    except Exception as e:
        print(f"処理完了記録エラー: {e}")
        print(f"コレクション名: {COLLECTION_NAME}, イベントID: {event_id}")
        return False


def mark_processing_failed(event_id: str, bucket_name: str, file_name: str) -> bool:
    """処理失敗時に再試行可能な状態へ戻す。

    try_start_processing は「ドキュメントが存在する＝処理中/済み」で重複判定するため、
    処理が途中で失敗して status='processing' のまま残ると、同じファイルが二度と
    処理できなくなる（expire_at もないので TTL でも消えない）。
    失敗時はドキュメントを削除して、再アップロード/再配信での再処理を可能にする。
    """
    try:
        db = _get_db()
        doc_ref = db.collection(COLLECTION_NAME).document(event_id)
        doc_ref.delete()
        print(f"処理失敗のため重複防止ドキュメントを削除（再試行可能化）: イベントID={event_id}")
        return True
    except Exception as e:
        print(f"処理失敗マークエラー: {e}")
        print(f"コレクション名: {COLLECTION_NAME}, イベントID: {event_id}")
        return False

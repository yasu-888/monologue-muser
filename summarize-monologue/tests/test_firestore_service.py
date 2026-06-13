from datetime import UTC, datetime

import firestore_service
from firestore_service import generate_event_id, mark_processing_failed


class _FakeDocRef:
    def __init__(self):
        self.deleted = False
        self.updated = None

    def delete(self):
        self.deleted = True

    def update(self, data):
        self.updated = data


class _FakeCollection:
    def __init__(self, doc_ref):
        self._doc_ref = doc_ref

    def document(self, event_id):
        return self._doc_ref


class _FakeDb:
    def __init__(self, doc_ref):
        self._doc_ref = doc_ref

    def collection(self, name):
        return _FakeCollection(self._doc_ref)


class TestGenerateEventId:
    def test_is_deterministic_for_same_inputs(self):
        a = generate_event_id("bucket", "file.m4a")
        b = generate_event_id("bucket", "file.m4a")
        assert a == b

    def test_differs_for_different_files(self):
        assert generate_event_id("b", "a.m4a") != generate_event_id("b", "c.m4a")


class TestMarkProcessingFailed:
    def test_deletes_document_to_allow_retry(self, monkeypatch):
        doc_ref = _FakeDocRef()
        monkeypatch.setattr(firestore_service, "_get_db", lambda: _FakeDb(doc_ref))

        ok = mark_processing_failed("eid", "bucket", "file.m4a")

        assert ok is True
        assert doc_ref.deleted is True

    def test_returns_false_when_delete_raises(self, monkeypatch):
        doc_ref = _FakeDocRef()
        doc_ref.delete = lambda: (_ for _ in ()).throw(RuntimeError("x"))
        monkeypatch.setattr(firestore_service, "_get_db", lambda: _FakeDb(doc_ref))

        assert mark_processing_failed("eid", "bucket", "file.m4a") is False


class TestMarkProcessingCompleted:
    def test_sets_timezone_aware_expire_at(self, monkeypatch):
        doc_ref = _FakeDocRef()
        monkeypatch.setattr(firestore_service, "_get_db", lambda: _FakeDb(doc_ref))

        firestore_service.mark_processing_completed("eid", "bucket", "file.m4a")

        expire_at = doc_ref.updated["expire_at"]
        assert isinstance(expire_at, datetime)
        # datetime.now(UTC) を使うので tz-aware であること。
        assert expire_at.tzinfo is not None
        completed_at = doc_ref.updated["completed_at"]
        assert (expire_at - completed_at).days == 10
        # utcnow() の naive datetime ではないことを念のため確認。
        assert completed_at.tzinfo == UTC

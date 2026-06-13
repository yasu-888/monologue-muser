import types

import main


def _cloud_event(bucket="bucket", name="20240101_abcd1234_メモ.m4a"):
    return types.SimpleNamespace(data={"bucket": bucket, "name": name})


class TestLocalTmpPath:
    def test_strips_directories_from_object_name(self):
        # GCS オブジェクト名にスラッシュが含まれても /tmp 直下の安全なパスになる。
        assert main._local_tmp_path("nested/dir/file.m4a") == "/tmp/file.m4a"

    def test_keeps_plain_name(self):
        assert main._local_tmp_path("file.m4a") == "/tmp/file.m4a"


def _patch_pipeline(monkeypatch, *, start=True, download=True, summary=None,
                    notion=True, recorder=None):
    recorder = recorder if recorder is not None else {}
    summary = summary or {"markdown": "m", "nextActions": [], "tags": ["t"]}

    monkeypatch.setattr(main, "generate_event_id", lambda *a: "eid")
    monkeypatch.setattr(main, "try_start_processing", lambda *a: start)
    monkeypatch.setattr(main, "download_file_from_gcs", lambda *a: download)
    monkeypatch.setattr(main, "transcribe_and_summarize", lambda *a: summary)
    monkeypatch.setattr(main, "send_to_notion", lambda *a: notion)
    monkeypatch.setattr(main, "delete_file_from_gcs", lambda *a: True)
    monkeypatch.setattr(main, "mark_processing_completed", lambda *a: True)

    def failed(*a):
        recorder["failed"] = True
        return True

    monkeypatch.setattr(main, "mark_processing_failed", failed)
    # 一時ファイル削除は副作用を持たせず観測のみ。
    monkeypatch.setattr(main.os.path, "exists", lambda p: False)
    return recorder


class TestSummarizeMonologue:
    def test_skips_when_already_processing(self, monkeypatch):
        rec = _patch_pipeline(monkeypatch, start=False)
        result = main.summarize_monologue(_cloud_event())
        assert result == "Event already processed or in progress"
        assert "failed" not in rec

    def test_happy_path_completes(self, monkeypatch):
        rec = _patch_pipeline(monkeypatch)
        result = main.summarize_monologue(_cloud_event())
        assert result == "処理が正常に完了しました"
        assert "failed" not in rec

    def test_download_failure_marks_failed_for_retry(self, monkeypatch):
        rec = _patch_pipeline(monkeypatch, download=False)
        main.summarize_monologue(_cloud_event())
        assert rec.get("failed") is True

    def test_notion_failure_marks_failed_for_retry(self, monkeypatch):
        rec = _patch_pipeline(monkeypatch, notion=False)
        main.summarize_monologue(_cloud_event())
        assert rec.get("failed") is True

    def test_unexpected_exception_marks_failed_for_retry(self, monkeypatch):
        rec = _patch_pipeline(monkeypatch)

        def boom(*a):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(main, "transcribe_and_summarize", boom)
        result = main.summarize_monologue(_cloud_event())
        assert result.startswith("Error:")
        assert rec.get("failed") is True

    def test_tmp_file_removed_in_finally(self, monkeypatch):
        _patch_pipeline(monkeypatch)
        removed = {}
        monkeypatch.setattr(main.os.path, "exists", lambda p: True)
        monkeypatch.setattr(main.os, "remove", lambda p: removed.setdefault("path", p))
        main.summarize_monologue(_cloud_event(name="dir/x.m4a"))
        assert removed["path"] == "/tmp/x.m4a"

import gemini_service
from schema import SummaryResponse, TranscriptionResponse, error_summary


class _FakeResponse:
    def __init__(self, parsed=None, text=None):
        self.parsed = parsed
        self.text = text


class _FakeFiles:
    def upload(self, file):
        return f"uploaded:{file}"


class _FakeModels:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"contents": contents, "schema": config["response_schema"]})
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.files = _FakeFiles()
        self.models = _FakeModels(responses)


def _install_client(monkeypatch, responses):
    client = _FakeClient(responses)
    monkeypatch.setattr(gemini_service, "_get_client", lambda: client)
    return client


class TestTranscribeAndSummarize:
    def test_returns_markdown_next_actions_and_tags_on_success(self, monkeypatch):
        transcription = TranscriptionResponse(transcription="これは独り言です")
        summary = SummaryResponse(
            markdown="### 話題\n本文", nextActions=["やる"], tags=["AI"]
        )
        _install_client(monkeypatch, [_FakeResponse(parsed=transcription),
                                      _FakeResponse(parsed=summary)])

        result = gemini_service.transcribe_and_summarize("/tmp/x.m4a")

        assert result == {"markdown": "### 話題\n本文", "nextActions": ["やる"], "tags": ["AI"]}

    def test_transcription_falls_back_to_text_when_parsed_is_none(self, monkeypatch):
        summary = SummaryResponse(markdown="m", nextActions=[], tags=["t"])
        client = _install_client(
            monkeypatch,
            [_FakeResponse(parsed=None, text="素のテキスト"), _FakeResponse(parsed=summary)],
        )

        gemini_service.transcribe_and_summarize("/tmp/x.m4a")

        # 2 回目（要約）のプロンプトにフォールバックした文字起こしが渡る。
        assert "素のテキスト" in client.models.calls[1]["contents"]

    def test_returns_symmetric_keys_on_transcription_error(self, monkeypatch):
        client = _FakeClient([])
        client.files.upload = lambda file: (_ for _ in ()).throw(RuntimeError("boom"))
        monkeypatch.setattr(gemini_service, "_get_client", lambda: client)

        result = gemini_service.transcribe_and_summarize("/tmp/x.m4a")

        assert set(result) == {"markdown", "nextActions", "tags"}
        assert result["nextActions"] == []
        assert result["tags"] == ["文字起こしエラー"]
        assert "boom" in result["markdown"]

    def test_returns_symmetric_keys_on_summary_error(self, monkeypatch):
        transcription = TranscriptionResponse(transcription="t")
        client = _FakeClient([_FakeResponse(parsed=transcription)])
        original = client.models.generate_content
        calls = {"n": 0}

        def flaky(model, contents, config):
            calls["n"] += 1
            if calls["n"] == 1:
                return original(model, contents, config)
            raise RuntimeError("summary boom")

        client.models.generate_content = flaky
        monkeypatch.setattr(gemini_service, "_get_client", lambda: client)

        result = gemini_service.transcribe_and_summarize("/tmp/x.m4a")

        assert result["tags"] == ["要約エラー"]
        assert result["nextActions"] == []


class TestErrorSummaryHelper:
    def test_has_same_keys_as_success_response(self):
        assert set(error_summary("msg", "kind")) == {"markdown", "nextActions", "tags"}

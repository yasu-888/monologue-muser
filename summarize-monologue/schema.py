from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    transcription: str = Field(description="ボイスメモの正確な文字起こし")


class SummaryResponse(BaseModel):
    markdown: str = Field(description="Notionに最適化されたMarkdown形式のまとめノート")
    nextActions: list[str] = Field(
        description="ボイスメモの内容から次にするべき行動をリスト化(0〜3個)"
    )
    # tags の説明は Gemini への指示の一部なので文言を変えない（プロンプト同等の仕様）。
    tags: list[str] = Field(
        description=(
            "notion_markdownの内容のトピックス・話題を見て、「タグ」を生成。"
            "何についての話題なのか簡単に特定できるように具体的かつ短い単語にしてください。"
            "（例：プログラミング、恋愛、AI、転職...）"
        )
    )


def error_summary(message: str, kind: str) -> dict:
    """Gemini 処理失敗時の戻り値を成功時 (SummaryResponse) と同じキー集合に揃える。

    main.py が markdown / nextActions / tags を無条件に参照できるよう、
    成功・失敗で戻り値の形を対称にするための共通ファクトリ。
    kind はタグ兼ログ用の失敗種別（例: "文字起こしエラー" / "要約エラー"）。
    """
    return {
        "markdown": f"# {kind}\n\n処理中にエラーが発生しました: {message}",
        "nextActions": [],
        "tags": [kind],
    }

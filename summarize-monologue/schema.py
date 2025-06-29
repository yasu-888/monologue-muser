from pydantic import BaseModel, Field
from typing import List

class TranscriptionResponse(BaseModel):
    transcription: str = Field(description="ボイスメモの正確な文字起こし")

class SummaryResponse(BaseModel):
    markdown: str = Field(description="Notionに最適化されたMarkdown形式のまとめノート"),
    nextActions: List[str] = Field(description="ボイスメモの内容から次にするべき行動をリスト化(0〜3個)"),
    tags: List[str] = Field(description="notion_markdownの内容のトピックス・話題を見て、「タグ」を生成。何についての話題なのか簡単に特定できるように具体的かつ短い単語にしてください。（例：プログラミング、恋愛、AI、転職...）")
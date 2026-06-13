import json
import os
import textwrap

from google import genai
from schema import SummaryResponse, TranscriptionResponse, error_summary

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'gemini_api_key')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

# genai.Client は import 時ではなく初回利用時に生成する。
# 認証なしのテスト環境で import できること、Cloud Run コールドスタートでの遅延初期化が目的。
_genai_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
    return _genai_client


# プロンプト文字列は仕様の一部。文言は変更しない。
_TRANSCRIPTION_PROMPT = textwrap.dedent("""
    <goal>ボイスメモの内容を正確に文字に起こしてください。</goal>
    <role>あなたは音声文字起こしの専門家で、話し言葉を正確にテキストに変換することが得意です。</role>
    <premise>この音声は独り言で考え事をしているボイスメモです。話題が突然変わったり、元の話題に戻ったりします。何か正解を出したいというよりは無数に浮かぶアイディアを言い連ねています。</premise>
    <goal-detail>
        <1>音声内容をできるだけ正確に文字に起こしてください。</1>
        <2>「ええと」や「あーー」などの言い淀みは除去して構いません。</2>
        <3>話し手の感情や語調のニュアンスをできるだけ残すようにしてください。</3>
        <4>文脈を無くさないように、話し言葉の自然な流れを維持してください。</4>
    </goal-detail>
    <output-format>
    純粋な文字起こしのテキストを出力してください。
    ```json
    {
        "transcription": "文字起こしの内容をここに記載"
    }
    ```
    </output-format>
    <instructions>
        <step1>ボイスメモを日本語で純粋に文字起こししてください。</step1>
        <step2>「ええと」や「あーー」など言葉に詰まっている部分を削除して、聞きやすい文章にしてください。</step2>
        <step3>話の流れや文脈、感情表現はそのまま保持してください。</step3>
        <step4>整形や要約はせず、元の発言内容をそのまま文字に起こしてください。</step4>
    </instructions>
""")


def _build_summary_prompt(transcription: str) -> str:
    # プロンプト文字列は仕様の一部。文言は変更しない。
    return textwrap.dedent(f"""
        <goal>文字起こしされたボイスメモの内容を整理して、きれいなメモにまとめてください。</goal>
        <role>あなたはソクラテスの弟子なみの聞き上手で、独り言のメモから情報が整理されたメモを作成することが得意です。</role>
        <premise>この文字起こしは独り言で考え事をしているボイスメモです。話題が突然変わったり、元の話題に戻ったりします。何か正解を出したいというよりは無数に浮かぶアイディアを言い連ねています。</premise>
        <goal-detail>
            <1>話題ごとに見出し（###）を作って、情報の順番を整理してください。話している順番に関わらず、設定した見出しに内容を足していってください。</1>
            <2>感情や心情を省略、要約せずに、できるだけニュアンスを残すようにしてください。</2>
            <3>箇条書きのようにきれいにまとめないでください。話の文脈を無くさないように、話し言葉口調のままの文章でまとめてください。</3>
            <4>整理はしますが、情報の要約はしないでください。内容の本質は保持してください。</4>
            <5>全体を見て「〇〇する！」「〇〇してみようかな」「〇〇興味ある」みたいに次の行動をするべきものを next-actionsにまとめてください。</5>
        </goal-detail>
        <output-format>
        Notionに適したMarkdown形式で出力してください。
        見出しは細かく作成することを意識し、1つの見出しに対して、最大でも150文字以内くらいにまとめてください。
        ```json
        {{
            "markdown": "### 話題1\\n内容1\\n内容2\\n### 話題2\\n内容1\\n内容2\\n### 話題3\\n内容1\\n内容2\\n...(いくつでも)",
            "nextActions": ["やること1", "やること2", "やること3"],
            "tags": ["タグ1", "タグ2", "タグ3"]
        }}
        ```
        </output-format>
        <instructions>
            <step1>このボイスメモを日本語で純粋に文字起こししてください。</step1>
            <step2>「ええと」や「あーー」など言葉に詰まっている部分などを削除して、きれいな文章にしてください。</step2>
            <step3>文章の中から話題（トピックス）を任意の数選定して、題名（タイトル）をつけ、マークダウンで見出し（###）を作ってください。タイトルはその話題の中での気づきや、結論などを短い文章にしたものを設定。イメージはインタビュー記事の段落ごとについているタイトルのような感じ。</step3>
            <step4>考え事の内容をできるだけ削らないようにして、各見出しの中にまとめてください。</step4>
            <step5>step4までの内容をまとめて、1つのMarkdownを出力してください。</step5>
            <step6>整理した内容の話題の中から「タグ」を最大3つ重要な順に生成してください。何についての話題なのか簡単に特定できるように具体的かつ短い単語にしてください。（例：プログラミング、英語、恋愛、AI、転職...）具体的な内容が分かりづらいものはやめて。</step6>
        </instructions>
        <transcription>
            {transcription}
        </transcription>
    """)  # noqa: E501  プロンプト本文は仕様であり改行で折り返せない


def _transcribe(file_path: str) -> str:
    """音声ファイルを文字起こししてテキストを返す。"""
    client = _get_client()
    audio_file = client.files.upload(file=file_path)

    transcription_response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[_TRANSCRIPTION_PROMPT, audio_file],
        config={
            'response_mime_type': 'application/json',
            'response_schema': TranscriptionResponse,
        },
    )
    parsed: TranscriptionResponse | None = transcription_response.parsed
    if parsed is not None:
        # structured output が取れたときはそれを使う。
        return json.loads(parsed.model_dump_json())['transcription']
    # parsed が None の場合は素のテキストへフォールバック（schema 適合に失敗した応答）。
    return transcription_response.text


def _summarize(transcription: str) -> dict:
    """文字起こしテキストを整形・要約し、SummaryResponse 相当の dict を返す。"""
    client = _get_client()
    summary_response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=_build_summary_prompt(transcription),
        config={
            'response_mime_type': 'application/json',
            'response_schema': SummaryResponse,
        },
    )
    parsed: SummaryResponse = summary_response.parsed
    return json.loads(parsed.model_dump_json())


def transcribe_and_summarize(file_path: str) -> dict:
    """音声ファイルを文字起こし→整形要約し、markdown / nextActions / tags を返す。

    成功・失敗のどちらでも同じキー集合（markdown / nextActions / tags）を返す。
    失敗種別ごとにエラー内容を markdown に残し、tags にエラー種別を入れることで、
    Notion 側でユーザーが失敗に気づけるようにする（現挙動を維持）。
    """
    try:
        transcription = _transcribe(file_path)
    except Exception as e:
        print(f"文字起こし中にエラーが発生しました: {e}")
        return error_summary(str(e), "文字起こしエラー")

    try:
        return _summarize(transcription)
    except Exception as e:
        print(f"文字起こしまたは要約中にエラーが発生しました: {e}")
        return error_summary(str(e), "要約エラー")

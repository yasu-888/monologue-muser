import notion_service
from notion_service import (
    NOTION_RICH_TEXT_LIMIT,
    convert_markdown_to_notion_blocks,
    extract_title_from_file_name,
    send_to_notion,
)


class TestExtractTitleFromFileName:
    def test_uses_third_segment_as_title(self):
        assert extract_title_from_file_name("20240101_abcd1234_買い物メモ.m4a") == "買い物メモ"

    def test_keeps_underscores_inside_title(self):
        # title 自体にアンダースコアが含まれても後半が欠落しない。
        assert (
            extract_title_from_file_name("20240101_abcd1234_今日_やる_こと.m4a")
            == "今日_やる_こと"
        )

    def test_falls_back_to_basename_when_too_few_segments(self):
        assert extract_title_from_file_name("memo.m4a") == "memo"
        assert extract_title_from_file_name("20240101_abcd.m4a") == "20240101_abcd"


class TestConvertMarkdownToNotionBlocks:
    def test_dash_lines_become_bulleted_list_items(self):
        blocks = convert_markdown_to_notion_blocks("- やること1\n- やること2")
        assert [b["type"] for b in blocks] == ["bulleted_list_item", "bulleted_list_item"]
        text = blocks[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"]
        assert text == "やること1"

    def test_headings_map_to_heading_levels(self):
        blocks = convert_markdown_to_notion_blocks("## h2\n### h3\n#### h4")
        assert [b["type"] for b in blocks] == ["heading_2", "heading_3", "heading_4"]

    def test_plain_lines_become_paragraphs(self):
        blocks = convert_markdown_to_notion_blocks("ふつうの文章")
        assert blocks[0]["type"] == "paragraph"

    def test_long_line_is_split_into_multiple_rich_text_chunks(self):
        long_line = "あ" * (NOTION_RICH_TEXT_LIMIT * 2 + 5)
        blocks = convert_markdown_to_notion_blocks(long_line)
        chunks = blocks[0]["paragraph"]["rich_text"]
        assert len(chunks) == 3
        assert all(len(c["text"]["content"]) <= NOTION_RICH_TEXT_LIMIT for c in chunks)
        assert "".join(c["text"]["content"] for c in chunks) == long_line


class _FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class TestSendToNotion:
    def test_returns_true_and_posts_title_and_tags(self, monkeypatch):
        captured = {}

        def fake_post(url, headers=None, json=None):
            captured["json"] = json
            return _FakeResponse(200)

        monkeypatch.setattr(notion_service.requests, "post", fake_post)

        ok = send_to_notion("20240101_abcd1234_買い物_メモ.m4a", "### 話題\n本文", "", ["買い物"])

        assert ok is True
        props = captured["json"]["properties"]
        assert props["Title"]["title"][0]["text"]["content"] == "買い物_メモ"
        assert props["Tags"]["multi_select"] == [{"name": "買い物"}]

    def test_returns_false_on_error_status(self, monkeypatch):
        monkeypatch.setattr(
            notion_service.requests, "post", lambda *a, **k: _FakeResponse(400, "bad")
        )
        assert send_to_notion("a_b_c.m4a", "x", "", []) is False

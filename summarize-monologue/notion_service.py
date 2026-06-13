import os

import requests

NOTION_API_KEY = os.environ.get('NOTION_API_KEY', 'your_notion_api_key')
NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID', 'your_notion_database_id')

# Notion API は rich_text の 1 要素あたり content 2000 文字までという制限がある。
# 超過すると 400 (validation_error) になるため、長い行は複数の rich_text 要素へ分割する。
# https://developers.notion.com/reference/request-limits
NOTION_RICH_TEXT_LIMIT = 2000


def extract_title_from_file_name(file_name: str) -> str:
    """ファイル名からタイトルを取り出す。

    ファイル名は `{timestamp}_{uuid8}_{title}.{ext}` 形式。title 自体に
    アンダースコアを含み得るため、3 番目以降を全て連結してタイトルとする。
    アンダースコアが 2 個未満（想定外の形式）の場合は、拡張子を除いた全体を
    タイトルとしてフォールバックする。
    """
    base_name = os.path.splitext(file_name)[0]
    parts = base_name.split("_")
    if len(parts) >= 3:
        return "_".join(parts[2:])
    return base_name


def _rich_text_chunks(content: str) -> list:
    """content を Notion の文字数制限ごとに分割した rich_text 要素のリストにする。"""
    if not content:
        return [{"type": "text", "text": {"content": ""}}]
    return [
        {"type": "text", "text": {"content": content[i:i + NOTION_RICH_TEXT_LIMIT]}}
        for i in range(0, len(content), NOTION_RICH_TEXT_LIMIT)
    ]


def _block(block_type: str, content: str) -> dict:
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": _rich_text_chunks(content)},
    }


def convert_markdown_to_notion_blocks(markdown_content):
    """Markdown を Notion ブロックのリストへ変換する。

    対応: heading_2/3/4 (`## `/`### `/`#### `)、bulleted_list_item (`- ` / `* `)、
    その他は paragraph。NextActions は `- ` 形式で生成されるため、箇条書きへ変換する。
    """
    blocks = []

    for raw_line in markdown_content.split('\n'):
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith('#### '):
            blocks.append(_block("heading_4", line[5:]))
        elif line.startswith('### '):
            blocks.append(_block("heading_3", line[4:]))
        elif line.startswith('## '):
            blocks.append(_block("heading_2", line[3:]))
        elif line.startswith('- ') or line.startswith('* '):
            blocks.append(_block("bulleted_list_item", line[2:]))
        else:
            blocks.append(_block("paragraph", line))

    return blocks


def send_to_notion(file_name, markdown_content, next_action_markdown, tags):
    """文字起こしと要約を Notion データベースへ送信する。成功で True。"""
    try:
        title = extract_title_from_file_name(file_name)

        notion_endpoint = "https://api.notion.com/v1/pages"

        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        content_blocks = convert_markdown_to_notion_blocks(markdown_content)

        data = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "Title": {"title": [{"text": {"content": title}}]},
                "Tags": {"multi_select": [{"name": tag} for tag in tags]},
            },
            "children": content_blocks,
        }

        if next_action_markdown:
            data["children"].append({
                "object": "block",
                "type": "divider",
                "divider": {},
            })
            data["children"].extend(convert_markdown_to_notion_blocks(next_action_markdown))

        response = requests.post(notion_endpoint, headers=headers, json=data)

        if response.status_code == 200:
            print("Notionへの送信に成功しました。")
            return True
        else:
            print(
                "Notionへの送信中にエラーが発生しました: "
                f"ステータスコード={response.status_code}, レスポンス={response.text}"
            )
            return False
    except Exception as e:
        print(f"Notionへの送信中に例外が発生しました: {e}")
        return False

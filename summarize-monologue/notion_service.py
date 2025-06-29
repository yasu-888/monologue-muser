import os
import requests
import json

NOTION_API_KEY = os.environ.get('NOTION_API_KEY', 'your_notion_api_key')
NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID', 'your_notion_database_id')

def convert_markdown_to_notion_blocks(markdown_content):
    """
    Markdown形式のコンテンツをNotionブロック形式に変換します。
    
    Args:
        markdown_content (str): Markdown形式のテキスト
        
    Returns:
        list: Notionブロックのリスト。
    """
    blocks = []
    lines = markdown_content.split('\n')
    
    for line in lines:
        line = line.strip()
        
        if not line:
            continue

        # 見出しの判定と変換
        if line.startswith('#### '):
            # heading_4
            blocks.append({
                "object": "block",
                "type": "heading_4",
                "heading_4": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": line[5:]
                            } # "#### "を除去
                        }
                    ]
                }
            })
        elif line.startswith('### '):
            # heading_3
            blocks.append({
                "object": "block",
                "type": "heading_3", 
                "heading_3": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": line[4:]
                            } # "### "を除去
                        }
                    ]
                }
            })
        elif line.startswith('## '):
            # heading_2
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": line[3:]
                            } # "## "を除去
                        }
                    ]
                }
            })
        else:
            # 通常のテキストは段落として扱う
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": line
                            } # 行の内容をそのまま使用
                        }
                    ]
                }
            })

    return blocks

def send_to_notion(file_name, markdown_content, next_action_markdown, tags):
    """
    Notion APIを使用して、文字起こしと要約をNotionデータベースに送信します。
    
    Args:
        file_name (str): 処理対象のファイル名。タイトル抽出に使用されます。
        markdown_content (str): Markdown形式の本文コンテンツ。
        next_action_markdown (str): 次の行動に関するMarkdown形式のコンテンツ。
        tags (list): 関連するタグのリスト。
        
    Returns:
        bool: 送信が成功した場合はTrue、失敗した場合はFalse。
    """
    try:
        # ファイル名からタイトルを取得
        base_name = os.path.splitext(file_name)[0]
        parts = base_name.split("_")
        title = parts[2]

        notion_endpoint = "https://api.notion.com/v1/pages"

        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        # マークダウンをNotionブロックに変換
        content_blocks = convert_markdown_to_notion_blocks(markdown_content) # 本文コンテンツをNotionブロックに変換
        
        # Notionに送信するデータ構造を作成
        data = {
            "parent": {
                "database_id": NOTION_DATABASE_ID
            },
            "properties": {
                "Title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                },
                "Tags": {
                    "multi_select": [{"name": tag} for tag in tags]
                }
            },
            "children": content_blocks
        }

        # NextActionがある場合は区切りと共に追加
        if next_action_markdown:
            data["children"].append(
                {
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                }
            )
            next_action_blocks = convert_markdown_to_notion_blocks(next_action_markdown) # NextActionコンテンツをNotionブロックに変換
            data["children"].extend(next_action_blocks)

        response = requests.post(notion_endpoint, headers=headers, json=data)

        if response.status_code == 200:
            print(f"Notionへの送信に成功しました。")
            return True
        else:
            print(f"Notionへの送信中にエラーが発生しました: ステータスコード={response.status_code}, レスポンス={response.text}")
            return False
    except Exception as e:
        print(f"Notionへの送信中に例外が発生しました: {e}")
        return False
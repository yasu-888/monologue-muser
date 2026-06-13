import os
import sys

# サービスディレクトリ直下のモジュール（main / *_service / schema）を import できるよう
# sys.path に追加する。upload-monologue と main.py 名が衝突するため、
# テストはサービス単位で実行する。
sys.path.insert(0, os.path.dirname(__file__))

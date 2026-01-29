"""
NotiGenie アプリケーション設定定数

ハードコードされたマジックナンバーを一元管理します。
環境変数でオーバーライド可能な設定も含みます。
"""
import os

# セッション管理
SESSION_HISTORY_LIMIT_MINUTES = int(os.environ.get("SESSION_HISTORY_LIMIT_MINUTES", "5"))
SESSION_MAX_HISTORY_LENGTH = int(os.environ.get("SESSION_MAX_HISTORY_LENGTH", "40"))

# Firestore コレクション名
FIRESTORE_SESSION_COLLECTION = "conversations"
FIRESTORE_SCHEMA_COLLECTION = "notion_schemas"

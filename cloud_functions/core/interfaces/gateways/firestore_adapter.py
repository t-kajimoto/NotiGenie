import datetime
import os
from google.cloud import firestore
from typing import List, Dict, Any
from ...domain.interfaces import ISessionRepository
from ...config import (
    SESSION_HISTORY_LIMIT_MINUTES,
    SESSION_MAX_HISTORY_LENGTH,
    FIRESTORE_SESSION_COLLECTION,
    FIRESTORE_SCHEMA_COLLECTION,
)
from ...logging_config import setup_logger

logger = setup_logger(__name__)

class FirestoreAdapter(ISessionRepository):
    """
    Firestoreを使用したセッション履歴管理の実装クラス。
    """

    def __init__(self):
        """
        初期化処理。Firestoreクライアントを生成します。
        環境変数 FIRESTORE_DATABASE が設定されている場合はそのデータベースを使用し、
        設定されていない場合はデフォルトデータベース ((default)) を使用します。
        """
        try:
            database_id = os.environ.get("FIRESTORE_DATABASE") or "(default)"
            # database引数はgoogle-cloud-firestore >= 2.0.0 で利用可能
            self.db = firestore.Client(database=database_id)
            self.session_collection_name = FIRESTORE_SESSION_COLLECTION
            self.schema_collection_name = FIRESTORE_SCHEMA_COLLECTION
            logger.info(f"Initialized Firestore Client with database: {database_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore Client: {e}")
            self.db = None

    def load_notion_schemas(self) -> Dict[str, Any]:
        """
        FirestoreからNotionのスキーマ定義を全て読み込みます。

        何をやっているか:
        1. 'notion_schemas' コレクションの全ドキュメントを取得します。
        2. 各ドキュメントについて、ドキュメントIDをキー（例: 'todo_list'）、
           ドキュメントのフィールド内容を値とする辞書を作成します。
        3. これにより、以前 `schemas.yaml` から読み込んでいたのと同じデータ構造を再現します。

        なぜやっているか:
        - NotionのDB IDのような機密情報や、頻繁に変更される可能性のあるスキーマ定義を
          ソースコードから分離するためです。
        - これにより、新しいDBを追加する際にデプロイが不要になります。

        Returns:
            Dict[str, Any]: Notionスキーマ定義の辞書。
                           エラーが発生した場合は空の辞書を返します。
        """
        if not self.db:
            logger.error("Cannot load Notion schemas: Firestore client is not initialized.")
            return {}

        try:
            schemas = {}
            docs = self.db.collection(self.schema_collection_name).stream()
            for doc in docs:
                schemas[doc.id] = doc.to_dict()

            if not schemas:
                logger.warning(f"No documents found in '{self.schema_collection_name}' collection. The application might not function correctly without Notion schemas.")
            else:
                logger.info(f"Successfully loaded {len(schemas)} Notion schemas from Firestore.")

            return schemas

        except Exception as e:
            logger.error(f"Error loading Notion schemas from Firestore: {e}")
            return {}

    def get_recent_history(self, session_id: str, limit_minutes: int) -> List[Dict[str, Any]]:
        """
        指定されたセッションIDの最近の会話履歴を取得します。
        """
        if not self.db:
            return []

        try:
            doc_ref = self.db.collection(self.session_collection_name).document(session_id)
            doc = doc_ref.get()

            if not doc.exists:
                return []

            data = doc.to_dict()
            updated_at = data.get("updated_at")

            if not updated_at:
                return []

            # FirestoreのTimestamp型はdatetimeオブジェクトとして取得できます（タイムゾーン付きUTC）
            # 比較のために現在時刻もUTCで取得します
            now = datetime.datetime.now(datetime.timezone.utc)

            # updated_atがnaiveなdatetimeの場合の対応（通常Firestoreからはawareが返りますが念のため）
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=datetime.timezone.utc)

            diff = now - updated_at

            if diff.total_seconds() > (limit_minutes * 60):
                # 期限切れの場合は履歴をクリア（ドキュメントを削除、または履歴フィールドを空にする）
                # ここでは履歴を返さないだけに留め、次のadd_interactionで上書きされる挙動とします
                logger.info(f"Session {session_id} expired. Last updated: {diff.total_seconds()}s ago.")
                return []

            history = data.get("history", [])
            # Geminiの履歴フォーマットの検証（念のため）
            valid_history = []
            for item in history:
                if isinstance(item, dict) and 'role' in item and 'parts' in item:
                    valid_history.append(item)

            return valid_history

        except Exception as e:
            logger.error(f"Error retrieving history from Firestore: {e}")
            return []

    def add_interaction(self, session_id: str, user_message: str, model_response: str):
        """
        新しいユーザー発言とAIの応答を履歴に追加します。
        ドキュメントサイズの肥大化を防ぐため、最新の20ターン（40要素）のみを保持します。

        Firestoreトランザクションを使用して、読み取り→書き込みをアトミックに処理し、
        同時リクエストによる競合状態を防ぎます。
        """
        if not self.db:
            return

        doc_ref = self.db.collection(self.session_collection_name).document(session_id)

        @firestore.transactional
        def update_in_transaction(transaction, doc_ref):
            # トランザクション内で読み取り
            doc = doc_ref.get(transaction=transaction)

            current_history = []
            if doc.exists:
                data = doc.to_dict()
                updated_at = data.get("updated_at")

                # 期限切れチェック
                if updated_at:
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=datetime.timezone.utc)
                    diff = now - updated_at

                    if diff.total_seconds() <= (SESSION_HISTORY_LIMIT_MINUTES * 60):
                        # 有効な履歴のみ抽出
                        history = data.get("history", [])
                        for item in history:
                            if isinstance(item, dict) and 'role' in item and 'parts' in item:
                                current_history.append(item)

            # 新しい履歴を追加
            new_history = current_history + [
                {"role": "user", "parts": [user_message]},
                {"role": "model", "parts": [model_response]}
            ]

            # 履歴の長さを制限
            max_history_length = SESSION_MAX_HISTORY_LENGTH
            if len(new_history) > max_history_length:
                new_history = new_history[-max_history_length:]

            # トランザクション内で書き込み
            transaction.set(doc_ref, {
                "history": new_history,
                "updated_at": firestore.SERVER_TIMESTAMP
            })

            return len(new_history)

        try:
            transaction = self.db.transaction()
            count = update_in_transaction(transaction, doc_ref)
            logger.info(f"Updated history for session {session_id}. Count: {count}")

        except Exception as e:
            logger.error(f"Error saving history to Firestore: {e}")


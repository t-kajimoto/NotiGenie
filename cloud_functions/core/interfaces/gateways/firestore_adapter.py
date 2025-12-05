import datetime
import os
from google.cloud import firestore
from typing import List, Dict, Any
from ...domain.interfaces import ISessionRepository
import logging

logger = logging.getLogger(__name__)

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
            database_id = os.environ.get("FIRESTORE_DATABASE", "(default)")
            # database引数はgoogle-cloud-firestore >= 2.0.0 で利用可能
            self.db = firestore.Client(database=database_id)
            self.collection_name = "conversations"
            logger.info(f"Initialized Firestore Client with database: {database_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore Client: {e}")
            self.db = None

    def get_recent_history(self, session_id: str, limit_minutes: int) -> List[Dict[str, Any]]:
        """
        指定されたセッションIDの最近の会話履歴を取得します。
        """
        if not self.db:
            return []

        try:
            doc_ref = self.db.collection(self.collection_name).document(session_id)
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
        """
        if not self.db:
            return

        try:
            doc_ref = self.db.collection(self.collection_name).document(session_id)

            # 5分（デフォルト）で期限切れチェックを行い、有効な履歴のみを取得
            current_history = self.get_recent_history(session_id, limit_minutes=5)

            new_history = current_history + [
                {"role": "user", "parts": [user_message]},
                {"role": "model", "parts": [model_response]}
            ]

            # 履歴の長さを制限（最新の40要素 = 20ターン分のみ保持）
            # Geminiは大量のコンテキストを扱えますが、Firestoreの1MB制限と
            # 課金（読み込みデータ量ではないが、処理効率）を考慮して制限を設けます。
            max_history_length = 40
            if len(new_history) > max_history_length:
                new_history = new_history[-max_history_length:]

            data = {
                "history": new_history,
                "updated_at": firestore.SERVER_TIMESTAMP
            }

            doc_ref.set(data)
            logger.info(f"Updated history for session {session_id}. Count: {len(new_history)}")

        except Exception as e:
            logger.error(f"Error saving history to Firestore: {e}")

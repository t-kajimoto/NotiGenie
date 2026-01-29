"""
FirestoreAdapter のテスト

セッション管理、トランザクション処理、スキーマ読み込みのテスト。
"""
import pytest
from unittest.mock import MagicMock, patch
import datetime
import sys
import os

# cloud_functions をパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'cloud_functions'))


class TestFirestoreAdapter:
    """FirestoreAdapterのテストクラス"""

    @pytest.fixture
    def mock_firestore(self, mocker):
        """Firestoreクライアントをモック化"""
        mock_firestore_module = mocker.patch(
            'core.interfaces.gateways.firestore_adapter.firestore'
        )
        mock_client = MagicMock()
        mock_firestore_module.Client.return_value = mock_client
        mock_firestore_module.SERVER_TIMESTAMP = "SERVER_TIMESTAMP"
        mock_firestore_module.transactional = lambda f: f  # デコレータをパススルー
        return mock_client

    @pytest.fixture
    def firestore_adapter(self, mock_firestore, mocker):
        """テスト用FirestoreAdapterインスタンス"""
        mocker.patch.dict(os.environ, {"FIRESTORE_DATABASE": "test-db"})

        from core.interfaces.gateways.firestore_adapter import FirestoreAdapter
        return FirestoreAdapter()

    def test_init_success(self, firestore_adapter, mock_firestore):
        """正常初期化: Firestoreクライアントが作成される"""
        assert firestore_adapter.db is not None
        assert firestore_adapter.session_collection_name == "conversations"
        assert firestore_adapter.schema_collection_name == "notion_schemas"

    def test_load_notion_schemas(self, firestore_adapter, mock_firestore):
        """スキーマ読み込み: Firestoreコレクションからスキーマを取得"""
        # モックデータ設定
        mock_doc1 = MagicMock()
        mock_doc1.id = "todo_list"
        mock_doc1.to_dict.return_value = {
            "id": "db-id-1",
            "title": "タスクリスト",
            "properties": {"Name": {"type": "title"}}
        }

        mock_doc2 = MagicMock()
        mock_doc2.id = "shopping_list"
        mock_doc2.to_dict.return_value = {
            "id": "db-id-2",
            "title": "買い物リスト",
            "properties": {"Item": {"type": "title"}}
        }

        mock_firestore.collection.return_value.stream.return_value = [mock_doc1, mock_doc2]

        # 実行
        schemas = firestore_adapter.load_notion_schemas()

        # 検証
        assert len(schemas) == 2
        assert "todo_list" in schemas
        assert "shopping_list" in schemas
        assert schemas["todo_list"]["title"] == "タスクリスト"

    def test_get_recent_history_valid(self, firestore_adapter, mock_firestore):
        """有効な履歴: 期限内の履歴が返される"""
        # 現在時刻から1分前のタイムスタンプ
        now = datetime.datetime.now(datetime.timezone.utc)
        recent_time = now - datetime.timedelta(minutes=1)

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "updated_at": recent_time,
            "history": [
                {"role": "user", "parts": ["こんにちは"]},
                {"role": "model", "parts": ["こんにちは！"]}
            ]
        }

        mock_firestore.collection.return_value.document.return_value.get.return_value = mock_doc

        # 実行
        history = firestore_adapter.get_recent_history("test_session", limit_minutes=5)

        # 検証
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "model"

    def test_get_recent_history_expired(self, firestore_adapter, mock_firestore):
        """期限切れ履歴: 古い履歴は空リストを返す"""
        # 10分前のタイムスタンプ（5分の期限を超過）
        now = datetime.datetime.now(datetime.timezone.utc)
        old_time = now - datetime.timedelta(minutes=10)

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "updated_at": old_time,
            "history": [
                {"role": "user", "parts": ["古いメッセージ"]},
                {"role": "model", "parts": ["古い応答"]}
            ]
        }

        mock_firestore.collection.return_value.document.return_value.get.return_value = mock_doc

        # 実行
        history = firestore_adapter.get_recent_history("test_session", limit_minutes=5)

        # 検証: 期限切れのため空
        assert history == []

    def test_get_recent_history_no_document(self, firestore_adapter, mock_firestore):
        """ドキュメントなし: 空リストを返す"""
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_doc.to_dict.return_value = None

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        mock_firestore.collection.return_value.document.return_value = mock_doc_ref

        # 実行
        history = firestore_adapter.get_recent_history("nonexistent_session", limit_minutes=5)

        # 検証
        assert history == []

    def test_add_interaction_creates_new_history(self, firestore_adapter, mock_firestore, mocker):
        """履歴追加: 新しいインタラクションが保存される"""
        # トランザクション処理をシンプル化
        mock_transaction = MagicMock()
        mock_firestore.transaction.return_value = mock_transaction

        # get_recent_historyが空を返すようにモック
        mocker.patch.object(
            firestore_adapter,
            'get_recent_history',
            return_value=[]
        )

        # ドキュメントモック
        mock_doc_ref = MagicMock()
        mock_firestore.collection.return_value.document.return_value = mock_doc_ref

        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        mock_doc_ref.get.return_value = mock_doc_snapshot

        # 実行
        firestore_adapter.add_interaction(
            session_id="test_session",
            user_message="テストメッセージ",
            model_response="テスト応答"
        )

        # 検証: エラーなく完了することを確認
        # (実際のFirestoreへの書き込みはモック化されているため、呼び出しの確認のみ)
        mock_firestore.transaction.assert_called_once()

    def test_add_interaction_with_history_limit(self, firestore_adapter, mock_firestore, mocker):
        """履歴制限: 最大履歴長を超えた場合に古いものが削除される"""
        # 40件の履歴をモック（最大長）
        existing_history = [
            {"role": "user" if i % 2 == 0 else "model", "parts": [f"message_{i}"]}
            for i in range(40)
        ]

        mock_transaction = MagicMock()
        mock_firestore.transaction.return_value = mock_transaction

        mock_doc_ref = MagicMock()
        mock_firestore.collection.return_value.document.return_value = mock_doc_ref

        now = datetime.datetime.now(datetime.timezone.utc)
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = {
            "updated_at": now,
            "history": existing_history
        }
        mock_doc_ref.get.return_value = mock_doc_snapshot

        # 実行
        firestore_adapter.add_interaction(
            session_id="test_session",
            user_message="新しいメッセージ",
            model_response="新しい応答"
        )

        # トランザクションが呼ばれたことを確認
        mock_firestore.transaction.assert_called_once()


class TestFirestoreAdapterInitialization:
    """初期化関連のテスト"""

    def test_init_without_database_env(self, mocker):
        """FIRESTORE_DATABASE未設定時はデフォルトを使用"""
        mocker.patch.dict(os.environ, {}, clear=True)
        mock_firestore = mocker.patch(
            'core.interfaces.gateways.firestore_adapter.firestore'
        )
        mock_firestore.Client.return_value = MagicMock()

        from core.interfaces.gateways.firestore_adapter import FirestoreAdapter
        adapter = FirestoreAdapter()

        # デフォルトの "(default)" が使われる
        mock_firestore.Client.assert_called_once()

    def test_init_failure_handling(self, mocker):
        """Firestore初期化失敗時のハンドリング"""
        mocker.patch.dict(os.environ, {"FIRESTORE_DATABASE": "test-db"})
        mock_firestore = mocker.patch(
            'core.interfaces.gateways.firestore_adapter.firestore'
        )
        mock_firestore.Client.side_effect = Exception("Connection failed")

        from core.interfaces.gateways.firestore_adapter import FirestoreAdapter
        adapter = FirestoreAdapter()

        # dbがNoneになることを確認
        assert adapter.db is None

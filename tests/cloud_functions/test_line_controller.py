"""
LineController のテスト

現在のクリーンアーキテクチャに対応したテストケース。
タイムアウト処理とpush_messageフォールバックを含む。

Note: このテストはLINE SDK (line-bot-sdk) がインストールされている環境でのみ実行されます。
      CI環境では requirements.txt により自動インストールされます。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import sys
import os

# LINE SDKがインストールされているかチェック
try:
    import linebot
    HAS_LINEBOT = True
except ImportError:
    HAS_LINEBOT = False

pytestmark = pytest.mark.skipif(not HAS_LINEBOT, reason="line-bot-sdk not installed")


class TestLineController:
    """LineControllerのテストクラス"""

    @pytest.fixture
    def mock_use_case(self):
        """モック化されたProcessMessageUseCase"""
        use_case = MagicMock()
        use_case.execute = AsyncMock(return_value="テスト応答です。")
        return use_case

    @pytest.fixture
    def line_controller(self, mock_use_case, mocker):
        """テスト用LineControllerインスタンス"""
        mocker.patch.dict(os.environ, {
            "LINE_CHANNEL_ACCESS_TOKEN": "test_token",
            "LINE_CHANNEL_SECRET": "test_secret"
        })

        # LINE SDK クライアントをモック化
        mocker.patch('cloud_functions.core.interfaces.controllers.line_controller.ApiClient')
        mock_messaging_api = mocker.patch(
            'cloud_functions.core.interfaces.controllers.line_controller.MessagingApi'
        )
        mocker.patch('cloud_functions.core.interfaces.controllers.line_controller.WebhookParser')

        from cloud_functions.core.interfaces.controllers.line_controller import LineController
        controller = LineController(use_case=mock_use_case)
        controller.messaging_api = mock_messaging_api.return_value
        return controller

    @pytest.fixture
    def mock_event(self):
        """モックのLINEイベント"""
        event = MagicMock()
        event.reply_token = "test_reply_token"
        event.message.text = "テストメッセージ"
        event.source.user_id = "test_user_id"
        return event

    @pytest.mark.asyncio
    async def test_handle_text_message_success(self, line_controller, mock_use_case, mock_event):
        """正常系: メッセージが処理されて返信される"""
        await line_controller._handle_text_message(mock_event)

        # ユースケースが呼ばれたか確認
        mock_use_case.execute.assert_called_once()
        call_args = mock_use_case.execute.call_args
        assert call_args[0][0] == "テストメッセージ"
        assert call_args[1]["session_id"] == "test_user_id"

        # reply_messageが呼ばれたか確認
        line_controller.messaging_api.reply_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_text_message_error(self, line_controller, mock_use_case, mock_event):
        """エラー時: エラーメッセージが返信される"""
        mock_use_case.execute = AsyncMock(side_effect=Exception("テストエラー"))

        await line_controller._handle_text_message(mock_event)

        # エラー時もreply_messageが呼ばれる
        line_controller.messaging_api.reply_message.assert_called()
        call_args = line_controller.messaging_api.reply_message.call_args
        # エラーメッセージが含まれているか確認
        message_text = call_args[0][0].messages[0].text
        assert "申し訳ありません" in message_text

    def test_init_without_credentials(self, mock_use_case, mocker):
        """認証情報がない場合は機能が無効化される"""
        mocker.patch.dict(os.environ, {
            "LINE_CHANNEL_ACCESS_TOKEN": "",
            "LINE_CHANNEL_SECRET": ""
        })

        # 新しいインスタンスを作成
        mocker.patch('cloud_functions.core.interfaces.controllers.line_controller.ApiClient')
        mocker.patch('cloud_functions.core.interfaces.controllers.line_controller.MessagingApi')
        mocker.patch('cloud_functions.core.interfaces.controllers.line_controller.WebhookParser')

        from cloud_functions.core.interfaces.controllers.line_controller import LineController
        controller = LineController(use_case=mock_use_case)

        assert controller.parser is None
        assert controller.messaging_api is None

    def test_init_with_credentials(self, line_controller):
        """認証情報がある場合は正常初期化される"""
        assert line_controller.channel_access_token == "test_token"
        assert line_controller.channel_secret == "test_secret"

    @pytest.mark.asyncio
    async def test_handle_request_with_valid_signature(self, line_controller, mocker):
        """有効な署名でWebhookが処理される"""
        # モックイベントを作成
        mock_event = MagicMock()
        mock_event.message.text = "テスト"
        mock_event.reply_token = "token"
        mock_event.source.user_id = "user123"

        line_controller.parser = MagicMock()
        line_controller.parser.parse.return_value = [mock_event]

        # isinstance チェックを常にTrueにする
        mocker.patch(
            'cloud_functions.core.interfaces.controllers.line_controller.isinstance',
            return_value=True
        )

        # _handle_text_messageをモック化
        line_controller._handle_text_message = AsyncMock()

        await line_controller.handle_request("body", "signature")

        line_controller.parser.parse.assert_called_once_with("body", "signature")
        line_controller._handle_text_message.assert_called_once_with(mock_event)


class TestLineControllerTimeout:
    """タイムアウト関連のテスト"""

    @pytest.fixture
    def mock_use_case(self):
        use_case = MagicMock()
        use_case.execute = AsyncMock(return_value="遅延応答")
        return use_case

    @pytest.fixture
    def line_controller_with_slow_response(self, mock_use_case, mocker):
        """タイムアウトテスト用のコントローラー"""
        mocker.patch.dict(os.environ, {
            "LINE_CHANNEL_ACCESS_TOKEN": "test_token",
            "LINE_CHANNEL_SECRET": "test_secret"
        })

        mocker.patch('cloud_functions.core.interfaces.controllers.line_controller.ApiClient')
        mock_messaging_api = mocker.patch(
            'cloud_functions.core.interfaces.controllers.line_controller.MessagingApi'
        )
        mocker.patch('cloud_functions.core.interfaces.controllers.line_controller.WebhookParser')

        from cloud_functions.core.interfaces.controllers.line_controller import LineController
        controller = LineController(use_case=mock_use_case)
        controller.messaging_api = mock_messaging_api.return_value
        return controller

    @pytest.mark.asyncio
    async def test_timeout_triggers_push_message(
        self, line_controller_with_slow_response, mock_use_case, mocker
    ):
        """タイムアウト時にpush_messageが使用される"""
        mock_event = MagicMock()
        mock_event.reply_token = "token"
        mock_event.message.text = "テスト"
        mock_event.source.user_id = "user123"

        # asyncio.wait_forがTimeoutErrorを投げるようモック
        original_wait_for = asyncio.wait_for

        async def mock_wait_for(coro, timeout):
            # 最初の呼び出しはタイムアウト
            raise asyncio.TimeoutError()

        mocker.patch('asyncio.wait_for', side_effect=mock_wait_for)

        controller = line_controller_with_slow_response
        await controller._handle_text_message(mock_event)

        # push_messageが呼ばれたか確認
        controller.messaging_api.push_message.assert_called()

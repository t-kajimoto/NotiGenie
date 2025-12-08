import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cloud_functions.core.use_cases.process_message import ProcessMessageUseCase

@pytest.fixture
def mock_language_model():
    """GeminiAdapterのモックを返すFixture"""
    mock = MagicMock()
    mock.select_databases = AsyncMock()
    mock.generate_tool_calls = AsyncMock()
    mock.generate_response = AsyncMock()
    return mock

@pytest.fixture
def mock_notion_repository():
    """NotionAdapterのモックを返すFixture"""
    mock = MagicMock()
    # テスト用にダミーのスキーマ情報を持たせる
    mock.notion_database_mapping = {
        "todo_list": {"id": "todo_list", "description": "タスク管理DB", "properties": {}},
        "diary": {"id": "diary", "description": "日記DB", "properties": {}}
    }
    # 各ツールもモック化
    mock.search_database = MagicMock(return_value={"result": "searched"})
    mock.create_page = MagicMock(return_value={"result": "created"})
    return mock

@pytest.fixture
def mock_session_repository():
    """FirestoreAdapterのモックを返すFixture"""
    mock = MagicMock()
    mock.get_recent_history = MagicMock(return_value=[])
    mock.add_interaction = MagicMock()
    return mock

@pytest.fixture
def use_case(mock_language_model, mock_notion_repository, mock_session_repository):
    """テスト対象のUseCaseインスタンスを返すFixture"""
    return ProcessMessageUseCase(
        language_model=mock_language_model,
        notion_repository=mock_notion_repository,
        session_repository=mock_session_repository
    )

@pytest.mark.asyncio
async def test_execute_single_db_success_flow(
    use_case, mock_language_model, mock_notion_repository, mock_session_repository
):
    """正常系: 単一DB → ツールコール生成 → 実行 → 応答生成 の一連の流れをテスト"""
    # --- Arrange ---
    user_utterance = "今日のタスクを教えて"
    current_date = "2023-10-27"
    session_id = "test_session"

    # Step 1: DB選択のモック
    mock_language_model.select_databases.return_value = ["todo_list"]

    # Step 2: ツールコール生成のモック
    mock_language_model.generate_tool_calls.return_value = [
        {"name": "search_database", "args": {"query": "今日のタスク", "database_name": "todo_list"}}
    ]

    # Step 3: 応答生成のモック
    mock_language_model.generate_response.return_value = "本日のタスクはこちらです..."

    # --- Act ---
    final_response = await use_case.execute(user_utterance, current_date, session_id)

    # --- Assert ---
    # 1. DB選択が呼ばれたか
    mock_language_model.select_databases.assert_awaited_once_with(
        user_utterance, current_date, []
    )
    # 2. ツールコール生成が呼ばれたか
    mock_language_model.generate_tool_calls.assert_awaited_once()
    # 3. Notionツールが呼ばれたか
    mock_notion_repository.search_database.assert_called_once_with(
        query="今日のタスク", database_name="todo_list"
    )
    # 4. 応答生成が呼ばれたか
    mock_language_model.generate_response.assert_awaited_once()
    # 5. 最終的な応答が正しいか
    assert final_response == "本日のタスクはこちらです..."
    # 6. セッションが保存されたか
    mock_session_repository.add_interaction.assert_called_once()

@pytest.mark.asyncio
async def test_execute_no_db_selected(
    use_case, mock_language_model, mock_notion_repository, mock_session_repository
):
    """DBが選択されなかった場合、雑談応答が返されることをテスト"""
    # --- Arrange ---
    user_utterance = "こんにちは"
    current_date = "2023-10-27"
    session_id = "test_session"

    # Step 1: DB選択の結果が空
    mock_language_model.select_databases.return_value = []
    # 雑談応答のモック
    mock_language_model.generate_response.return_value = "こんにちは！何かお手伝いできることはありますか？"

    # --- Act ---
    final_response = await use_case.execute(user_utterance, current_date, session_id)

    # --- Assert ---
    # ツールコール生成やNotionツールは呼ばれない
    mock_language_model.generate_tool_calls.assert_not_called()
    mock_notion_repository.search_database.assert_not_called()
    # generate_responseは呼ばれる
    mock_language_model.generate_response.assert_awaited_once_with(user_utterance, [], [])
    # 応答が正しいか
    assert final_response == "こんにちは！何かお手伝いできることはありますか？"
    # セッションは保存される
    mock_session_repository.add_interaction.assert_called_once()

@pytest.mark.asyncio
async def test_execute_multiple_dbs_selected(
    use_case, mock_language_model, mock_notion_repository
):
    """複数DBが選択された場合のフローをテスト"""
    # --- Arrange ---
    user_utterance = "今日のタスクと日記を検索して"

    # DB選択で2つ返す
    mock_language_model.select_databases.return_value = ["todo_list", "diary"]

    # generate_tool_callsがDBごとに異なる結果を返すように設定
    mock_language_model.generate_tool_calls.side_effect = [
        [{"name": "search_database", "args": {"query": "今日のタスク", "database_name": "todo_list"}}],
        [{"name": "search_database", "args": {"query": "今日の日記", "database_name": "diary"}}]
    ]

    mock_language_model.generate_response.return_value = "検索結果です。"

    # --- Act ---
    await use_case.execute(user_utterance, "2023-10-27", "test_session")

    # --- Assert ---
    # generate_tool_callsが2回呼ばれている
    assert mock_language_model.generate_tool_calls.call_count == 2
    # Notionのsearch_databaseが2回呼ばれている
    assert mock_notion_repository.search_database.call_count == 2
    # generate_responseに2つのツール実行結果が渡されている
    mock_language_model.generate_response.assert_awaited_once()
    # generate_responseに渡されたtool_results引数の長さを確認
    args, _ = mock_language_model.generate_response.await_args
    assert len(args[1]) == 2 # args[1] は tool_results

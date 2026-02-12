import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cloud_functions.core.use_cases.process_message import ProcessMessageUseCase

@pytest.fixture
def mock_language_model():
    """GeminiAdapterのモックを返すFixture"""
    mock = MagicMock()
    # select_databases は統合DB化に伴い廃止
    mock.generate_tool_calls = AsyncMock()
    mock.generate_response = AsyncMock()
    mock.perform_research = AsyncMock()
    return mock

@pytest.fixture
def mock_notion_repository():
    """NotionAdapterのモックを返すFixture"""
    mock = MagicMock()
    # 統合データベース (master_db) のスキーマ
    mock.notion_database_mapping = {
        "master_db": {
            "id": "test_master_db_id",
            "title": "タスク・買い物・献立管理",
            "description": "統合データベース。買い物、ToDo、献立を一元管理します。",
            "properties": {
                "タイトル": {"type": "title", "description": "タスクやアイテムの名前"},
                "カテゴリ": {"type": "select", "options": ["Shopping", "ToDo", "Menu", "Other"], "description": "データの種類"},
                "メモ": {"type": "rich_text", "description": "詳細情報"},
                "予定日": {"type": "date", "description": "明確な日付"},
                "予定日表示": {"type": "rich_text", "description": "自然言語での時期"},
                "完了日": {"type": "date", "description": "完了した日付"}
            }
        }
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
        session_repository=mock_session_repository,
        help_message="ヘルプメッセージです"
    )

@pytest.mark.asyncio
async def test_execute_help_keyword(use_case, mock_language_model):
    """ヘルプキーワードが入力された場合、即座にヘルプメッセージを返す"""
    # --- Arrange ---
    user_utterances = ["help", "ヘルプ", "へるぷ", " HELP ", "ヘルプ  "]
    current_date = "2023-10-27"
    session_id = "test_session"

    for utterance in user_utterances:
        # --- Act ---
        response = await use_case.execute(utterance, current_date, session_id)

        # --- Assert ---
        assert response == "ヘルプメッセージです"
        # 外部APIは呼ばれないこと
        mock_language_model.generate_tool_calls.assert_not_called()
        mock_language_model.generate_tool_calls.reset_mock()

@pytest.mark.asyncio
async def test_execute_unified_db_success_flow(
    use_case, mock_language_model, mock_notion_repository, mock_session_repository
):
    """正常系: 統合DB (master_db) → ツールコール生成 → 実行 → 応答生成"""
    # --- Arrange ---
    user_utterance = "今日のタスクを教えて"
    current_date = "2023-10-27"
    session_id = "test_session"

    # DB選択は廃止。常に master_db が使われる。

    # Step 2: ツールコール生成のモック (Multi-turn: 1回目=ツール, 2回目=終了)
    mock_language_model.generate_tool_calls.side_effect = [
        [{"name": "search_database", "args": {"query": "今日のタスク", "database_name": "master_db"}}],
        []
    ]

    # Step 3: 応答生成のモック
    mock_language_model.generate_response.return_value = "本日のタスクはこちらです..."

    # --- Act ---
    final_response = await use_case.execute(user_utterance, current_date, session_id)

    # --- Assert ---
    # 1. ツールコール生成が呼ばれたか (master_dbのスキーマが渡される)
    # ループ処理のため複数回呼ばれる可能性があるが、少なくとも1回は呼ばれる
    assert mock_language_model.generate_tool_calls.call_count >= 1
    # 2. Notionツールが呼ばれたか
    mock_notion_repository.search_database.assert_called_once_with(
        query="今日のタスク", database_name="master_db"
    )
    # 3. 応答生成が呼ばれたか
    mock_language_model.generate_response.assert_awaited_once()
    # 4. 最終的な応答が正しいか
    assert final_response == "本日のタスクはこちらです..."
    # 5. セッションが保存されたか
    mock_session_repository.add_interaction.assert_called_once()

@pytest.mark.asyncio
async def test_execute_shopping_creation(
    use_case, mock_language_model, mock_notion_repository
):
    """統合DB: 買い物アイテム作成のシナリオをテスト"""
    # --- Arrange ---
    user_utterance = "牛乳を買いたい"
    current_date = "2024-01-01"

    # ツールコール生成
    expected_properties = {
        "カテゴリ": "Shopping",
        "予定日": "2024-01-01",
        "予定日表示": "今日"
    }
    # Multi-turn mock
    mock_language_model.generate_tool_calls.side_effect = [
        [{
            "name": "create_page",
            "args": {
                "database_name": "master_db",
                "title": "牛乳",
                "properties": expected_properties
            }
        }],
        []
    ]

    mock_language_model.generate_response.return_value = "牛乳を買い物リストに追加しました。"

    # --- Act ---
    final_response = await use_case.execute(user_utterance, current_date, "test_session")

    # --- Assert ---
    # ツールコール生成が呼ばれたか
    assert mock_language_model.generate_tool_calls.call_count >= 1

    # Notionのcreate_pageが期待通りの引数で呼ばれたか
    mock_notion_repository.create_page.assert_called_once_with(
        database_name="master_db",
        title="牛乳",
        properties=expected_properties
    )

    # 最終応答が正しいか
    assert final_response == "牛乳を買い物リストに追加しました。"

@pytest.mark.asyncio
async def test_execute_meal_creation_with_category(
    use_case, mock_language_model, mock_notion_repository
):
    """統合DB: 食事記録作成 (カテゴリ=Menu) のシナリオをテスト"""
    # --- Arrange ---
    user_utterance = "昨日の夜、家でカレーを食べた"
    current_date = "2024-01-01"

    # ツールコール生成
    expected_properties = {
        "カテゴリ": "Menu",
        "完了日": "2023-12-31",
        "予定日": "2023-12-31",
        "メモ": "夜ごはん、家で食べた"
    }
    mock_language_model.generate_tool_calls.side_effect = [
        [{
            "name": "create_page",
            "args": {
                "database_name": "master_db",
                "title": "カレー",
                "properties": expected_properties
            }
        }],
        []
    ]

    # 応答生成
    mock_language_model.generate_response.return_value = "食事内容を記録しました。"

    # --- Act ---
    final_response = await use_case.execute(user_utterance, current_date, "test_session")

    # --- Assert ---
    assert mock_language_model.generate_tool_calls.call_count >= 1

    mock_notion_repository.create_page.assert_called_once_with(
        database_name="master_db",
        title="カレー",
        properties=expected_properties
    )

    assert final_response == "食事内容を記録しました。"

@pytest.mark.asyncio
async def test_execute_with_research(
    use_case, mock_language_model, mock_notion_repository
):
    """リサーチ (Google検索) 結果がツールコール生成に渡されることをテスト"""
    # --- Arrange ---
    user_utterance = "渋谷の美味しいラーメン屋に行きたい"
    current_date = "2024-01-01"

    # リサーチ結果
    mock_language_model.perform_research.return_value = "渋谷おすすめラーメン: 一蘭渋谷店 (住所: ...)"

    # ツールコール生成
    mock_language_model.generate_tool_calls.side_effect = [
        [{
            "name": "create_page",
            "args": {
                "database_name": "master_db",
                "title": "渋谷のラーメン屋に行く",
                "properties": {
                    "カテゴリ": "ToDo",
                    "メモ": "渋谷おすすめラーメン: 一蘭渋谷店 (住所: ...)"
                }
            }
        }],
        []
    ]

    mock_language_model.generate_response.return_value = "ラーメン屋を登録しました。"

    # --- Act ---
    await use_case.execute(user_utterance, current_date, "test_session")

    # --- Assert ---
    # リサーチが呼ばれたか
    mock_language_model.perform_research.assert_awaited_once()
    # ツールコール生成にリサーチ結果が渡されたか
    call_kwargs = mock_language_model.generate_tool_calls.call_args
    assert "research_results" in call_kwargs.kwargs or len(call_kwargs.args) > 5

@pytest.mark.asyncio
async def test_execute_with_notion_error(
    use_case, mock_language_model, mock_notion_repository, mock_session_repository
):
    """Notionのcreate_pageがエラーを返した場合、エラー情報がgenerate_responseに渡されることをテスト"""
    # --- Arrange ---
    user_utterance = "牛乳を追加して"
    current_date = "2024-01-01"

    # ツールコール生成
    mock_language_model.generate_tool_calls.side_effect = [
        [{
            "name": "create_page",
            "args": {
                "database_name": "master_db",
                "title": "牛乳",
                "properties": {"カテゴリ": "Shopping"}
            }
        }],
        []
    ]

    # Notionのcreate_pageがエラーを返す
    error_result = {"error": "Notion API Error in create_page: validation_error - body failed validation."}
    mock_notion_repository.create_page.return_value = error_result

    # 応答生成 (エラー時のメッセージ)
    mock_language_model.generate_response.return_value = "申し訳ありません、Notionへの登録に失敗しました。"

    # --- Act ---
    final_response = await use_case.execute(user_utterance, current_date, "test_session")

    # --- Assert ---
    # 1. create_pageが呼ばれたか
    mock_notion_repository.create_page.assert_called_once()

    # 2. generate_responseにエラー結果が渡されたか
    call_args = mock_language_model.generate_response.call_args
    tool_results = call_args[0][1]  # 第2引数 = tool_results
    assert len(tool_results) == 1
    assert tool_results[0]["name"] == "create_page"
    assert "error" in tool_results[0]["result"]

    # 3. 最終応答が返されたか
    assert final_response == "申し訳ありません、Notionへの登録に失敗しました。"

    # 4. セッションが保存されたか（エラー時でも会話は保存）
    mock_session_repository.add_interaction.assert_called_once()

@pytest.mark.asyncio
async def test_execute_multi_turn_search_then_create(
    use_case, mock_language_model, mock_notion_repository
):
    """マルチターン: 検索(0件) → 判断 → 作成 のフローをテスト"""
    # --- Arrange ---
    user_utterance = "池上梅園に行きたい"
    current_date = "2024-01-01"

    # Mock sequence:
    # 1. First turn: Search
    # 2. Second turn: Create (based on empty search result)
    # 3. Third turn: Finish (empty list)
    mock_language_model.generate_tool_calls.side_effect = [
        [{"name": "search_database", "args": {"query": "池上梅園"}}],
        [{"name": "create_page", "args": {"database_name": "master_db", "title": "池上梅園", "properties": {"カテゴリ": "ToDo"}}}],
        []
    ]
    
    # Mock Notion results
    # 1. Search returns empty
    mock_notion_repository.search_database.return_value = {"results": []}
    # 2. Create returns success
    mock_notion_repository.create_page.return_value = {"id": "new-page-id", "url": "http://notion..."}

    mock_language_model.generate_response.return_value = "池上梅園をToDoに追加しました。"

    # --- Act ---
    final_response = await use_case.execute(user_utterance, current_date, "test_session")

    # --- Assert ---
    # 3回呼ばれる (Call 1: Search, Call 2: Create, Call 3: Finish)
    assert mock_language_model.generate_tool_calls.call_count == 3
    
    # Check intermediate history usage
    # 2nd call should include result of search
    call_args_list = mock_language_model.generate_tool_calls.call_args_list
    
    # 2回目の呼び出しの kwargs['current_turn_history'] に 1回目の結果(Search)が含まれているか
    second_call_kwargs = call_args_list[1].kwargs
    history_arg = second_call_kwargs['current_turn_history']
    assert len(history_arg) >= 2 # Model call + Function response
    
    # Model part
    # Note: dict structure depends on implementation in process_message.py
    # We implemented: {"role": "model", "parts": [{"function_call": ...}]}
    assert history_arg[0]['role'] == 'model'
    assert history_arg[0]['parts'][0]['function_call']['name'] == 'search_database'
    
    # Function part
    # {"role": "function", "parts": [{"function_response": ...}]}
    assert history_arg[1]['role'] == 'function'
    assert history_arg[1]['parts'][0]['function_response']['name'] == 'search_database'

    # Notion calls
    mock_notion_repository.search_database.assert_called_once()
    mock_notion_repository.create_page.assert_called_once()
    
    assert final_response == "池上梅園をToDoに追加しました。"

@pytest.mark.asyncio
async def test_execute_create_with_vague_date(
    use_case, mock_language_model, mock_notion_repository
):
    """曖昧な日付(未定)の抽出テスト"""
    # --- Arrange ---
    user_utterance = "ハネムーンに行きたい"
    current_date = "2024-01-01"

    # ツールコール生成
    # 期待されるプロパティ: 予定日表示="未定"
    mock_language_model.generate_tool_calls.side_effect = [
        [{
            "name": "create_page",
            "args": {
                "database_name": "master_db",
                "title": "ハネムーン",
                "properties": {
                    "カテゴリ": "ToDo",
                    "予定日表示": "未定" # ここが重要
                }
            }
        }],
        []
    ]

    mock_language_model.generate_response.return_value = "ハネムーンをToDo（未定）に追加しました。"

    # --- Act ---
    final_response = await use_case.execute(user_utterance, current_date, "test_session")

    # --- Assert ---
    args = mock_language_model.generate_tool_calls.call_args_list[0].args
    # 実際には引数の中身を検証したいが、mockのside_effectで定義したものが呼ばれる前提
    # create_pageが正しい引数で呼ばれたかを確認
    mock_notion_repository.create_page.assert_called_once()
    call_kwargs = mock_notion_repository.create_page.call_args.kwargs
    assert call_kwargs["title"] == "ハネムーン"
    assert call_kwargs["properties"]["予定日表示"] == "未定"

@pytest.mark.asyncio
async def test_execute_create_with_period_expression(
    use_case, mock_language_model, mock_notion_repository
):
    """期間表現(今年中)の抽出テスト"""
    # --- Arrange ---
    user_utterance = "ハネムーンに今年中に行きたい"
    current_date = "2024-01-01"

    # ツールコール生成
    # 期待されるプロパティ: 予定日表示="今年中"
    mock_language_model.generate_tool_calls.side_effect = [
        [{
            "name": "create_page",
            "args": {
                "database_name": "master_db",
                "title": "ハネムーン",
                "properties": {
                    "カテゴリ": "ToDo",
                    "予定日表示": "今年中"
                }
            }
        }],
        []
    ]

    mock_language_model.generate_response.return_value = "ハネムーンをToDo（今年中）に追加しました。"

    # --- Act ---
    final_response = await use_case.execute(user_utterance, current_date, "test_session")

    # --- Assert ---
    mock_notion_repository.create_page.assert_called_once()
    call_kwargs = mock_notion_repository.create_page.call_args.kwargs
    assert call_kwargs["title"] == "ハネムーン"
    assert call_kwargs["properties"]["予定日表示"] == "今年中"

@pytest.mark.asyncio
async def test_execute_with_history(
    use_case, mock_language_model, mock_session_repository
):
    """会話履歴が正しくLLMに渡されることを確認"""
    # --- Arrange ---
    user_utterance = "続き"
    current_date = "2024-01-01"
    
    # 過去の履歴
    history_data = [
        {"role": "user", "parts": ["前回の発言"]},
        {"role": "model", "parts": ["前回の応答"]}
    ]
    mock_session_repository.get_recent_history.return_value = history_data
    
    mock_language_model.generate_tool_calls.side_effect = [[], []] # No tools
    mock_language_model.generate_response.return_value = "応答"

    # --- Act ---
    await use_case.execute(user_utterance, current_date, "test_session")

    # --- Assert ---
    # get_recent_historyが呼ばれたか
    mock_session_repository.get_recent_history.assert_called_once()
    
    # generate_tool_callsに履歴が渡されたか
    # historyは5番目の位置引数 (user_utterance, current_date, tools, single_db_schema, history)
    call_args = mock_language_model.generate_tool_calls.call_args
    assert call_args.args[4] == history_data


"""
E2E テスト用フィクスチャ

実際の Gemini API と Notion テスト用 DB を使用します。
テスト中に作成されたページは teardown で自動削除されます。

使い方:
  1. tests/e2e/.env.test に実際の GEMINI_API_KEY と NOTION_API_KEY を設定
  2. pytest tests/e2e/ -v -s で実行
"""

import os
import sys
import pytest
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "cloud_functions"))

# .env.test から実APIキーをロード
env_path = Path(__file__).parent / ".env.test"
load_dotenv(env_path, override=True)

# ---------------------------------------------------------------------------
# テスト用DB定義
# ---------------------------------------------------------------------------
TEST_DB_ID = "3051ac9c-8c70-812f-9acc-e15173a81bba"

TEST_DB_SCHEMA = {
    "test_master_db": {
        "title": "E2Eテスト用DB",
        "id": TEST_DB_ID,
        "description": "E2Eテスト専用。master_db と同一スキーマ。",
        "properties": {
            "タイトル": {"type": "title", "description": "タスクやアイテムの名前"},
            "カテゴリ": {
                "type": "select",
                "options": ["Shopping", "TODO", "Menu", "Other"],
                "description": "データの種類",
            },
            "メモ": {"type": "rich_text", "description": "詳細情報、補足、URLなど"},
            "予定日": {"type": "date", "description": "明確な日付"},
            "予定日表示": {"type": "rich_text", "description": "自然言語での時期"},
            "完了日": {"type": "date", "description": "完了した日付"},
        },
    }
}

# スキーマを master_db としても参照可能にする (system_instruction が master_db を参照するため)
TEST_DB_SCHEMA["master_db"] = {
    **TEST_DB_SCHEMA["test_master_db"],
    "id": TEST_DB_ID,
}


# ---------------------------------------------------------------------------
# APIキー検証
# ---------------------------------------------------------------------------
def _check_api_keys():
    gemini = os.environ.get("GEMINI_API_KEY", "")
    notion = os.environ.get("NOTION_API_KEY", "")
    if not gemini or gemini.startswith("your-") or gemini == "dummy":
        pytest.skip("GEMINI_API_KEY が未設定です。tests/e2e/.env.test を確認してください。")
    if not notion or notion.startswith("your-") or notion == "dummy":
        pytest.skip("NOTION_API_KEY が未設定です。tests/e2e/.env.test を確認してください。")


# ---------------------------------------------------------------------------
# フィクスチャ: Notion Adapter（テスト用DB）
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def notion_adapter():
    """テスト用DBを使う NotionAdapter を返す。"""
    _check_api_keys()
    from cloud_functions.core.interfaces.gateways.notion_adapter import NotionAdapter
    adapter = NotionAdapter(notion_database_mapping=TEST_DB_SCHEMA)
    return adapter


# ---------------------------------------------------------------------------
# フィクスチャ: Gemini Adapter
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def gemini_adapter():
    """実APIキーを使う GeminiAdapter を返す。"""
    _check_api_keys()
    from cloud_functions.core.interfaces.gateways.gemini_adapter import GeminiAdapter

    # プロンプトファイルの読み込み
    prompts_dir = ROOT_DIR / "cloud_functions" / "prompts"
    system_instruction = (prompts_dir / "system_instruction.md").read_text(encoding="utf-8")
    response_instruction = (prompts_dir / "response_instruction.md").read_text(encoding="utf-8")

    adapter = GeminiAdapter(
        system_instruction_template=system_instruction,
        notion_database_mapping=TEST_DB_SCHEMA,
        response_instruction=response_instruction,
    )
    return adapter


# ---------------------------------------------------------------------------
# フィクスチャ: ProcessMessageUseCase
# ---------------------------------------------------------------------------
class InMemorySessionRepository:
    """E2Eテスト用の簡易セッションリポジトリ。Firestoreは使わない。"""

    def __init__(self):
        self._history = {}

    def get_recent_history(self, session_id: str, limit_minutes: int = 60):
        return self._history.get(session_id, [])

    def save_history(self, session_id: str, history: list):
        self._history[session_id] = history

    def update_history(self, session_id: str, new_entries: list):
        current = self._history.get(session_id, [])
        current.extend(new_entries)
        self._history[session_id] = current


@pytest.fixture(scope="function")
def use_case(gemini_adapter, notion_adapter):
    """
    テスト用の ProcessMessageUseCase を返す。
    セッション履歴はインメモリ。Notion はテスト用DB。
    """
    from cloud_functions.core.use_cases.process_message import ProcessMessageUseCase

    session_repo = InMemorySessionRepository()
    uc = ProcessMessageUseCase(
        language_model=gemini_adapter,
        notion_repository=notion_adapter,
        session_repository=session_repo,
    )
    # db_schemas をテスト用スキーマで上書き
    uc.db_schemas = TEST_DB_SCHEMA
    return uc


# ---------------------------------------------------------------------------
# フィクスチャ: クリーンアップ（テスト終了後にNotionページを削除）
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def created_page_ids():
    """テスト中に作成されたページIDを収集するリスト。"""
    return []


@pytest.fixture(autouse=True)
def cleanup_notion_pages(notion_adapter, created_page_ids, request):
    """テスト終了後に作成されたページをアーカイブ（削除）する。"""
    yield
    for page_id in created_page_ids:
        try:
            notion_adapter.client.pages.update(page_id=page_id, archived=True)
            print(f"  [CLEANUP] Archived page: {page_id}")
        except Exception as e:
            print(f"  [CLEANUP WARNING] Failed to archive {page_id}: {e}")

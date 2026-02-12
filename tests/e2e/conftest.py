"""
E2E テスト用フィクスチャ

実際の Gemini API、Notion テスト用 DB、Firestore（chat-history）を使用します。
テスト中に作成されたリソースは teardown で自動削除されます。

使い方:
  1. tests/e2e/.env.test に実際のAPIキーを設定 (.env.test.example を参考)
  2. pytest tests/e2e/ -v -s で実行
"""

import os
import sys
import uuid
import pytest
from pathlib import Path
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Pytest Option: --keep-notion (Cleanup無効化)
# ---------------------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption(
        "--keep-notion",
        action="store_true",
        default=False,
        help="テスト終了後にNotionページを削除せずに残す（手動確認用）",
    )


# ---------------------------------------------------------------------------
# パス設定: プロジェクトルートと cloud_functions をインポート可能にする
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "cloud_functions"))

# ---------------------------------------------------------------------------
# 環境変数: .env.test から実APIキーをロード
# ---------------------------------------------------------------------------
env_path = Path(__file__).parent / ".env.test"
load_dotenv(env_path, override=True)

# ---------------------------------------------------------------------------
# テスト用DB定義
# テスト用DB は本番 master_db と同一スキーマだが、別のNotionデータベースを使用する
# ---------------------------------------------------------------------------
TEST_DB_ID = "3051ac9c-8c70-812f-9acc-e15173a81bba"

TEST_DB_SCHEMA = {
    # master_db としてマッピング（system_instruction が master_db を参照するため）
    "master_db": {
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

# テスト用セッションIDのプレフィックス（クリーンアップ時に識別するため）
TEST_SESSION_PREFIX = "e2e-test-"


# ---------------------------------------------------------------------------
# APIキー検証: キーが設定されていない場合はテストをスキップ
# ---------------------------------------------------------------------------
def _check_api_keys():
    """E2Eテストに必要な全APIキーが設定されているか検証する。"""
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
# フィクスチャ: Firestore Adapter（実接続）
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def firestore_adapter():
    """
    実際のFirestoreに接続する FirestoreAdapter を返す。
    環境変数 FIRESTORE_DATABASE で接続先DBを制御する（デフォルト: chat-history）。
    """
    _check_api_keys()
    # GOOGLE_APPLICATION_CREDENTIALS が設定されているか確認
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not creds:
        pytest.skip("GOOGLE_APPLICATION_CREDENTIALS が未設定です。tests/e2e/.env.test を確認してください。")

    from cloud_functions.core.interfaces.gateways.firestore_adapter import FirestoreAdapter
    adapter = FirestoreAdapter()
    if not adapter.db:
        pytest.skip("Firestoreへの接続に失敗しました。")
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
# フィクスチャ: ProcessMessageUseCase（全コンポーネント実接続）
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def use_case(gemini_adapter, notion_adapter, firestore_adapter):
    """
    全コンポーネントが実APIに接続された ProcessMessageUseCase を返す。
    Gemini API → 本物, Notion → テスト用DB, Firestore → 実接続
    """
    from cloud_functions.core.use_cases.process_message import ProcessMessageUseCase

    uc = ProcessMessageUseCase(
        language_model=gemini_adapter,
        notion_repository=notion_adapter,
        session_repository=firestore_adapter,
    )
    # db_schemas をテスト用スキーマで上書き（テスト用DBのIDを使わせるため）
    uc.db_schemas = TEST_DB_SCHEMA
    return uc


# ---------------------------------------------------------------------------
# フィクスチャ: テストごとに一意のセッションIDを生成
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def session_id():
    """テスト用の一意なセッションIDを生成する。"""
    return f"{TEST_SESSION_PREFIX}{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# フィクスチャ: テスト中に作成されたNotionページIDを収集
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def created_page_ids():
    """テスト中に作成されたページIDを収集するリスト。"""
    return []


# ---------------------------------------------------------------------------
# 自動クリーンアップ: テスト終了後にNotionページとFirestoreセッションを削除
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def cleanup_test_resources(request, notion_adapter, firestore_adapter, created_page_ids, session_id):
    """テスト終了後に作成されたリソースを自動削除する（--keep-notion 指定時はスキップ）。"""
    yield

    # --keep-notion オプションが指定されている場合はCleanupをスキップ
    if request.config.getoption("--keep-notion"):
        if created_page_ids:
            print(f"\n  [KEEP] Processed Notion pages (not archived): {created_page_ids}")
        # Firestoreのセッションも残す場合はここをコメントアウトするなど調整可能だが、
        # 基本的にはNotionページが見たいはずなので、セッションは消しても良いかもしれない。
        # 一旦、ユーザー要望は「Notionページ」なので、Notionだけスキップする形にするが、
        # 続けて対話したいならセッションも残すべき。今回は両方残す。
        print(f"  [KEEP] Firestore session: {session_id}")
        return

    # 1. Notionページをアーカイブ（削除）
    for page_id in created_page_ids:
        try:
            notion_adapter.client.pages.update(page_id=page_id, archived=True)
            print(f"  [CLEANUP] Archived Notion page: {page_id}")
        except Exception as e:
            print(f"  [CLEANUP WARNING] Failed to archive page {page_id}: {e}")

    # 2. Firestoreのテスト用セッション履歴を削除
    try:
        doc_ref = firestore_adapter.db.collection(
            firestore_adapter.session_collection_name
        ).document(session_id)
        doc = doc_ref.get()
        if doc.exists:
            doc_ref.delete()
            print(f"  [CLEANUP] Deleted Firestore session: {session_id}")
    except Exception as e:
        print(f"  [CLEANUP WARNING] Failed to delete session {session_id}: {e}")

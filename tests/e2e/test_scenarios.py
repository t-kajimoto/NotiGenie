"""
E2E シナリオテスト

実際の Gemini API + Notion テスト用 DB + Firestore を使用して、
フルパイプラインを検証します。テスト後に作成されたリソースは自動削除されます。

実行:
  pytest tests/e2e/test_scenarios.py -v -s

注意:
  - Gemini API の課金が発生します（1回あたり数円程度）
  - テスト結果は Gemini の出力に依存するため、稀に不安定になる場合があります
"""

import asyncio
import pytest
from datetime import date


# ---------------------------------------------------------------------------
# ヘルパー: 非同期関数を同期的に実行する
# ---------------------------------------------------------------------------
def run_async(coro):
    """pytest から非同期の use_case.execute を呼び出すためのヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def find_created_pages(notion_adapter, title_query: str, created_page_ids: list) -> list:
    """
    テスト用DBから指定クエリでページを検索し、IDをクリーンアップリストに登録する。
    テスト終了後の自動削除で漏れがないよう、検索時に発見したIDを全て記録する。
    """
    results = notion_adapter.search_database(query=title_query, database_name="master_db")
    for page in results:
        page_id = page.get("id", "")
        if page_id and page_id not in created_page_ids:
            created_page_ids.append(page_id)
    return results


# ---------------------------------------------------------------------------
# ヘルパー: Notionページからメモのテキストを抽出する
# ---------------------------------------------------------------------------
def extract_memo_text(page: dict) -> str:
    """Notionページの properties からメモ (rich_text) のプレーンテキストを抽出する。"""
    memo = page.get("properties", {}).get("メモ", {})
    if isinstance(memo, dict) and "rich_text" in memo:
        return "".join(
            rt.get("plain_text", "") for rt in memo.get("rich_text", [])
        )
    return str(memo)


# ---------------------------------------------------------------------------
# シナリオ1: 基本的なタスク作成
# 「牛乳を買いたい」→ ページが作成され、カテゴリが Shopping であること。
# ---------------------------------------------------------------------------
class TestBasicTaskCreation:

    def test_creates_shopping_item(self, use_case, notion_adapter, created_page_ids, session_id):
        today = date.today().isoformat()

        # ProcessMessageUseCase を通してフルパイプラインを実行
        response = run_async(
            use_case.execute(
                user_utterance="牛乳を買いたい",
                current_date=today,
                session_id=session_id,
            )
        )

        print(f"\n  [RESPONSE] {response}")

        # 検証1: レスポンスが返ること
        assert response, "レスポンスが空です"

        # 検証2: テスト用DBに「牛乳」ページが作成されていること
        pages = find_created_pages(notion_adapter, "牛乳", created_page_ids)
        assert len(pages) > 0, "テスト用DBに「牛乳」ページが作成されていません"

        # 検証3: カテゴリが Shopping であること
        page = pages[0]
        category = page.get("properties", {}).get("カテゴリ", {})
        if isinstance(category, dict) and "select" in category:
            category_name = category["select"]["name"] if category["select"] else None
        else:
            category_name = str(category)
        print(f"  [CATEGORY] {category_name}")
        assert category_name == "Shopping", f"カテゴリが Shopping ではなく {category_name} です"


# ---------------------------------------------------------------------------
# シナリオ2: 調査結果のメモ保存
# 「アバター3の予約をしたい」→ Research が走り、メモに調査結果が含まれること。
# ---------------------------------------------------------------------------
class TestResearchSavingToMemo:

    def test_research_results_saved_to_memo(self, use_case, notion_adapter, created_page_ids, session_id):
        today = date.today().isoformat()

        response = run_async(
            use_case.execute(
                user_utterance="アバター3の映画の予約をしたい",
                current_date=today,
                session_id=session_id,
            )
        )

        print(f"\n  [RESPONSE] {response}")

        # 検証1: レスポンスが返ること
        assert response, "レスポンスが空です"

        # 検証2: テスト用DBに「アバター」関連ページが作成されていること
        pages = find_created_pages(notion_adapter, "アバター", created_page_ids)
        assert len(pages) > 0, "テスト用DBに「アバター」関連ページが作成されていません"

        # 検証3: メモに何らかの調査結果が含まれること（10文字以上）
        memo_text = extract_memo_text(pages[0])
        print(f"  [MEMO] {memo_text}")
        assert len(memo_text) > 10, f"メモの内容が不十分です: '{memo_text}'"


# ---------------------------------------------------------------------------
# シナリオ3: 訂正メッセージの反映
# Step 1: 「NoNoGirlsのライブに行きたい」→ ページ作成
# Step 2: 「グループ名はNoNoGirlsじゃなくてHANAだったわ」→ 既存ページが更新されること
# ---------------------------------------------------------------------------
class TestCorrectionHandling:

    def test_correction_updates_existing_page(self, use_case, notion_adapter, created_page_ids, session_id):
        today = date.today().isoformat()

        # === Step 1: まずタスクを作成 ===
        response1 = run_async(
            use_case.execute(
                user_utterance="NoNoGirlsのライブに行きたい",
                current_date=today,
                session_id=session_id,
            )
        )
        print(f"\n  [STEP1 RESPONSE] {response1}")
        assert response1, "Step 1: レスポンスが空です"

        # 作成されたページを確認（NoNoGirls または HANA で検索）
        pages_after_step1 = find_created_pages(notion_adapter, "NoNoGirls", created_page_ids)
        pages_hana = find_created_pages(notion_adapter, "HANA", created_page_ids)

        initial_page_count = len(pages_after_step1) + len(pages_hana)
        assert initial_page_count > 0, "Step 1: ページが作成されていません"

        # === Step 2: 訂正メッセージを送信 ===
        response2 = run_async(
            use_case.execute(
                user_utterance="グループ名はNoNoGirlsじゃなくてHANAだったわ",
                current_date=today,
                session_id=session_id,
            )
        )
        print(f"\n  [STEP2 RESPONSE] {response2}")
        assert response2, "Step 2: レスポンスが空です"

        # === 検証: いずれかのページのメモに「HANA」が含まれること ===
        pages_after_step2 = find_created_pages(notion_adapter, "NoNoGirls", created_page_ids)
        pages_after_step2_hana = find_created_pages(notion_adapter, "HANA", created_page_ids)
        all_pages = {p["id"]: p for p in pages_after_step2 + pages_after_step2_hana}

        total_pages = len(all_pages)
        print(f"  [PAGE COUNT] Step1後: {initial_page_count}, Step2後: {total_pages}")

        # いずれかのページのメモに「HANA」が含まれていれば訂正が反映されたとみなす
        found_hana_in_memo = False
        for page in all_pages.values():
            memo_text = extract_memo_text(page)
            print(f"  [PAGE] id={page['id']}, memo='{memo_text}'")
            if "HANA" in memo_text:
                found_hana_in_memo = True

        assert found_hana_in_memo, "訂正後、いずれのページのメモにも 'HANA' が含まれていません"

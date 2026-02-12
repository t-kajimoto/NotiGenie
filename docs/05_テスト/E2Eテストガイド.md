# E2Eテストガイド

本プロジェクトでは、プロンプト変更やロジック修正の影響をデプロイ前に検証するため、**本番相当の環境（実API）** を使用したE2Eテスト基盤を構築しています。

## 概要

### テスト構成

- **Gemini API**: 本物のモデルを使用（例: `gemini-2.0-flash-exp`）
- **Notion API**: テスト専用のデータベース（`master_db` と同スキーマ）を使用
- **Firestore**: 本物の `chat-history` データベースを使用（テスト用セッション生成）

### ディレクトリ構造

```
tests/e2e/
├── conftest.py          # 実APIキー読み込み、テスト用DBスキーマ、自動クリーンアップ
├── test_scenarios.py    # シナリオベースのE2Eテストコード
├── interactive_chat.py  # 対話型の手動テストツール
├── .env.test            # APIキー設定（git非管理）
└── google-credential.json # Firestore認証キー（git非管理）
```

---

## セットアップ

### 1. APIキーの設定

`tests/e2e/.env.test` を作成し、以下のキーを設定してください（`.env.example` 参考）。

```ini
GEMINI_API_KEY=your_gemini_api_key
NOTION_API_KEY=your_notion_api_key
GOOGLE_APPLICATION_CREDENTIALS=tests/e2e/google-credential.json
```

### 2. Firestore認証キーの配置

`tests/e2e/google-credential.json` にサービスアカウントキー（JSON）を配置してください。

---

## テスト実行方法

### 自動テスト (pytest)

全シナリオ（タスク作成、検索、訂正）を自動実行します。

```bash
# 通常実行（テスト終了後に作成データは自動削除されます）
pytest tests/e2e/ -v -s

# 作成データを残したい場合（Notion上で確認したい場合）
pytest tests/e2e/ -v -s --keep-notion
```

### 手動テスト (Interactive Chat)

コマンドラインでボットと直接対話して動作を確認できます。作成されたページは**削除されません**。

```bash
python tests/e2e/interactive_chat.py
```

終了後に表示されるURLから、Notion上の結果を即座に確認できます。

---

## テストシナリオ

`tests/e2e/test_scenarios.py` には以下のシナリオが実装されています。

1. **基本タスク作成**
   - 入力: 「牛乳を買いたい」
   - 検証: Notionベージが作成され、カテゴリがShopping、タイトルが牛乳になっていること。

2. **調査結果の保存**
   - 入力: 「アバター3の予約をしたい」
   - 検証: GeminiがGoogle検索を行い、その結果（上映日など）がNotionのメモ欄に保存されること。

3. **訂正フロー**
   - 入力: 「NoNoGirlsじゃなくてHANAだった」
   - 検証: 直前の会話で作成したページが検索され、タイトルやメモが適切に更新（上書き）されること。

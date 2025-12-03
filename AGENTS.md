# AGENTS.md

このファイルは、AIエージェント（Julesなど）がこのプロジェクトを理解し、開発・テストを行うためのガイドラインです。

## プロジェクト概要

NotiGenieは、Raspberry Pi上で動作し、音声コマンドを受け付けてNotionを操作するアプリケーションです。
以下のフローで動作します：
1.  物理ボタンを押して音声録音開始。
2.  ボタンを離すと録音終了。
3.  音声をテキスト化 (Google Cloud Speech-to-Text)。
4.  テキストから意図を解釈 (Google Gemini API)。
5.  Notion APIを実行。
6.  実行結果を音声でフィードバック (gTTS)。

### アーキテクチャ

Clean Architecture風のレイヤードアーキテクチャを採用しています。
*   `src/domain`: ビジネスロジック、ユースケース、エンティティ。外部依存なし。
*   `src/adapter`: 外部サービス（Gemini, Notion, STT）へのアダプター、コントローラー。
*   `src/hardware`: Raspberry Pi固有のハードウェア制御（GPIO, マイク入力）。
*   `src/main.py`: DIコンテナの役割を果たし、各層をつなぎ合わせるエントリーポイント。

## 環境構築と実行手順 (Jules環境用)

Jules環境（Linuxサンドボックス）では、Raspberry Pi固有のハードウェア（GPIO, オーディオ入力）が使用できません。
そのため、モックやダミーモードを利用してテストを行います。

### 1. 依存関係のインストール

`RPi.GPIO` や `sounddevice` などのハードウェア依存ライブラリは、インストールに失敗する可能性があるため、
`requirements.txt` を直接使うのではなく、必要なライブラリのみをインストールします。

```bash
# 仮想環境の作成と有効化
python3 -m venv venv
source venv/bin/activate

# 依存関係のインストール（ハードウェア依存を除外）
cp requirements.txt requirements_linux.txt
sed -i '/RPi.GPIO/d' requirements_linux.txt
sed -i '/sounddevice/d' requirements_linux.txt
sed -i '/gTTS/d' requirements_linux.txt
pip install -r requirements_linux.txt
pip install pytest pytest-asyncio pytest-mock mcp
```

### 2. 設定ファイルの準備

テスト実行には `.env` と `src/config.yaml` が必要です。

```bash
# config.yaml の作成
cp src/config.yaml.example src/config.yaml

# .env の作成 (ダミー値で可)
echo "GEMINI_API_KEY=dummy" > .env
echo "NOTION_API_KEY=dummy" >> .env
```

### 3. テストの実行

`pytest` を使用して、ビジネスロジックとアダプター層のテストを行います。
`tests/` ディレクトリ以下のテストは、外部APIをモックしているため、APIキーがダミーでも通過します。

```bash
pytest tests/
```

**注意:** `src/poc/` 以下のファイルは概念実証コードであり、テストスイートには含めません。

### 4. アプリケーションの起動 (シミュレーション)

`src/main.py` を実行すると、ハードウェアが見つからない場合は自動的にダミーモードになります。
コンソール入力 (Enterキー) でボタン押下をシミュレートできます。

```bash
# 実行 (バックグラウンド実行を推奨、または入力を自動化)
python src/main.py
```

ただし、自動テスト（CI/CD的なフロー）では、対話的な入力が難しいため、基本的には `pytest` での検証を優先してください。

## 開発ガイドライン

### 言語設定
*   **プラン提示やチャットは必ず日本語で行ってください。**
*   コミットメッセージやPRの記述も日本語を推奨します（英語でも可）。

### 開発フロー
1.  タスクの内容を理解し、`src/` 以下のコードを確認して影響範囲を特定する。
2.  **プランの作成**: 修正方針をステップごとに日本語で記述し、`set_plan` する。
3.  **テスト駆動開発**: 可能な限り、再現テストや新規機能のテストを先に書く（または修正と同時に書く）。
4.  **実装**: アーキテクチャを守り、責務を分離して実装する。
    *   外部API呼び出しはGateway層に閉じ込める。
    *   ハードウェア依存はHardware層に閉じ込める。
5.  **検証**: `pytest` を実行し、既存機能が壊れていないことを確認する。
6.  **コミット**: わかりやすいコミットメッセージで変更を保存する。

### アーキテクチャの遵守
*   **Domain層 (`src/domain`)**: 外部ライブラリ（Notion SDKなど）に依存させないこと。純粋なPythonオブジェクトで構成する。
*   **Adapter層 (`src/adapter`)**: ここで外部ライブラリを使用し、Domain層のインターフェースに合わせて変換する。
*   **Hardware層 (`src/hardware`)**: ハードウェア固有の処理はここに記述し、PC環境でも動くようにモック（ダミーモード）を用意する。

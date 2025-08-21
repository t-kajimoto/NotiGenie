# Docker 環境 設計書

本ドキュメントは、NotiGenieプロジェクトの開発および実行環境をコンテナ化するためのDocker設定について設計したものである。

## 1. 設計目標

- **開発環境の統一**: 開発者ごとに環境差異が生じるのを防ぎ、誰でも同じ環境でアプリケーションを開発・実行できるようにする。
- **ポータビリティ**: Raspberry Pi上での本番運用と、ローカルマシンでの開発を、同じDockerイメージをベースに実現する。
- **再現性**: 依存ライブラリのバージョンを固定し、常に同じ環境を再現できるようにする。

## 2. 作成ファイル一覧

本設計に基づき、以下のファイルを作成・管理する。

- `Dockerfile`
- `requirements.txt`
- `.dockerignore`
- `.env.example`

## 3. 各ファイルの詳細設計

### 3.1. `Dockerfile`

アプリケーションの実行環境を定義する。

- **ベースイメージ**: `python:3.12-slim-bookworm`
    - 理由: プロジェクトの要件であるRaspberry Pi (ARMアーキテクチャ)での動作を保証しつつ、軽量な`slim`バリアントを選択。Pythonバージョンは安定している`3.12`系を使用。
- **作業ディレクトリ**: `/app`
    - コンテナ内での作業基準点を設定。
- **依存関係のインストール**:
    - まず`requirements.txt`のみをコピーし、`pip install`を実行する。これにより、ソースコードの変更時にもpipのキャッシュが効き、ビルド時間を短縮できる。
- **ソースコードのコピー**:
    - `src`ディレクトリをコンテナ内の作業ディレクトリにコピーする。
- **実行コマンド**: `CMD ["python", "main.py"]`
    - コンテナ起動時に、アプリケーションのエントリポイントである`main.py`を実行する。

### 3.2. `requirements.txt`

Pythonの依存ライブラリとそのバージョンを管理する。

```
mcp-notion
google-generativeai
google-cloud-speech
gTTS
RPi.GPIO
```
- **選定理由**: プロジェクト要件に基づき、Notion連携、AI機能、音声合成、Raspberry PiのGPIO制御に必要なライブラリを選定。

### 3.3. `.dockerignore`

Dockerイメージに不要なファイルを含めないようにするための除外リスト。

- **除外対象**:
    - Git関連ファイル (`.git`, `.gitignore`)
    - Pythonキャッシュ (`__pycache__`)
    - ドキュメント (`*.md`, `docs/`)
    - ローカル環境ファイル (`.env`, `.venv`など)
- **目的**: ビルド時間の短縮、イメージサイズの削減、およびセキュリティの向上。

### 3.4. `.env.example`

必要な環境変数を定義するテンプレートファイル。

- **定義変数**:
    - `NOTION_API_KEY`: Notion APIの認証トークン
    - `NOTION_VERSION`: Notion APIのバージョン
    - `GEMINI_API_KEY`: Gemini APIのキー
    - `GOOGLE_APPLICATION_CREDENTIALS`: Google Cloud認証情報のパス
- **目的**: 開発者がどの環境変数を設定する必要があるかを明確にする。実際のキーを記載した`.env`ファイルは`.gitignore`によりリポジトリから除外され、セキュリティを保つ。

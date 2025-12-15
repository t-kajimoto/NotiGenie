# NotiGenie

[![CI/CD for Cloud Functions](https://github.com/notigenie/NotiGenie/actions/workflows/cloud_functions_ci.yml/badge.svg)](https://github.com/notigenie/NotiGenie/actions/workflows/cloud_functions_ci.yml)
[![CI for Raspberry Pi](https://github.com/notigenie/NotiGenie/actions/workflows/raspberry_pi_ci.yml/badge.svg)](https://github.com/notigenie/NotiGenie/actions/workflows/raspberry_pi_ci.yml)

**NotiGenie (ノティジーニー)** は、音声やテキストでNotionデータベースを操作できるAIアシスタントです。
Raspberry Piによる音声操作、またはLINE Botによるテキスト操作に対応しています。

![NotiGenie Demo](https://user-images.githubusercontent.com/12345/your-demo-image.gif)
*(デモ画像や動画をここに挿入)*

## ✨ 主な機能

- **音声によるNotion操作**: 「買い物リストに牛乳を追加して」のように話しかけるだけで、Notionのデータベースにアイテムを追加・更新・検索できます。
- **マルチモーダル対応**: Raspberry Piを使った音声インターフェースと、LINE Botを使ったテキストインターフェースの両方で利用可能です。
- **高度な自然言語理解**: GoogleのGeminiモデルを利用し、曖昧な指示でも意図を汲み取って適切な操作を実行します。
- **柔軟なデータベース連携**: Firestoreにスキーマを登録するだけで、様々なNotionデータベースに対応させることができます。

## 📖 使い方

### Raspberry Piの場合
1. 「ねぇ、ジニー」とウェイクワードを呼びかけます。
2. LEDが点灯したら、用件を話しかけます。（例：「今日のタスクを教えて」）
3. NotiGenieがNotionデータベースを操作し、結果を音声で返します。

### LINEの場合
1. NotiGenieのLINE公式アカウントを友達追加します。
2. テキストメッセージで用件を送ります。（例：「読書リストに新しい本を追加」）
3. NotiGenieがNotionを操作し、結果をテキストで返します。

## 🛠️ アーキテクチャと設計
本システムは、クライアント（Raspberry Pi / LINE）とバックエンド（Google Cloud Functions）で構成されています。
バックエンドではクリーンアーキテクチャを採用し、LLMのFunction Calling機能を活用してNotion APIと連携しています。

より詳細な設計情報については、以下のドキュメントを参照してください。

- **[アーキテクチャ設計書](./docs/architecture.md)**: システム全体の構成図と各コンポーネントの役割について説明しています。
- **[Function Calling設計書](./docs/functions.md)**: LLMが使用するツール（関数）の詳細と、Notion APIとの対応関係について説明しています。
- **[開発・運用ガイド](./docs/development.md)**: デプロイ手順や、新しいNotionデータベースを連携させる方法について説明しています。

## 🚀 自分の環境へのデプロイ
このプロジェクトを自身の環境にデプロイする方法は、**[開発・運用ガイド](./docs/development.md)** を参照してください。
ガイドには、以下の内容が含まれています。
- 必要なGoogle Cloudプロジェクトのセットアップ
- IAMロールの設定
- 必要なAPIキーと環境変数
- GitHub Actionsを使った自動デプロイの方法

## ディレクトリ構成
```
.
├── .github/workflows/      # CI/CDワークフロー
├── cloud_functions/        # バックエンド (Google Cloud Functions)
│   └── core/               # クリーンアーキテクチャのコア層
├── raspberry_pi/           # クライアント (Raspberry Pi)
├── docs/                   # 設計ドキュメント
├── tests/                  # 各種テストコード
└── README.md
```

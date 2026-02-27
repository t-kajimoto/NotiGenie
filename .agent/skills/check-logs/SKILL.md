---
description: NotiGenieのCloud Functions/Cloud Runログを調査するスキル。エラー調査や動作確認に使用。
---

# NotiGenie ログ確認スキル

NotiGenieのCloud Functions（Cloud Run上で動作）のログをGCPから取得して調査するためのスキルです。
LINE botが応答しない、エラーが発生したなどの問題調査に使用します。

## 基本情報

| 項目              | 値                                 |
| ----------------- | ---------------------------------- |
| GCPプロジェクトID | `notigenie`                        |
| サービス名        | `notigenie-backend`                |
| リージョン        | `asia-northeast1`                  |
| タイムゾーン      | ログはUTCで保存。JST = UTC + 9時間 |

## ログ取得手順

### 1. 特定の時間帯のログを取得する

ユーザーが指定した時間帯のログを取得します。**ユーザーはJSTで指定するので、UTCに変換すること。**

```powershell
# 例: JST 18:00〜19:00 のログ → UTC 09:00〜10:00
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="notigenie-backend" AND timestamp>="2026-02-25T09:00:00Z" AND timestamp<="2026-02-25T10:00:00Z"' --project=notigenie --limit=100 --format=json 2>&1 | Out-File -FilePath C:\tmp\notigenie_logs.json -Encoding UTF8
```

> **重要**: `C:\tmp` ディレクトリが存在しない場合は事前に `New-Item -Path C:\tmp -ItemType Directory -Force` を実行すること。

### 2. エラーログのみ取得する

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="notigenie-backend" AND timestamp>="2026-02-25T09:00:00Z" AND timestamp<="2026-02-25T10:00:00Z" AND (severity="ERROR" OR severity="WARNING" OR severity="CRITICAL")' --project=notigenie --limit=50 --format="table(timestamp,severity,textPayload)" 2>&1
```

### 3. 簡易的にCloud Functions用コマンドで取得する

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; gcloud functions logs read notigenie-backend --region=asia-northeast1 --limit=100 --start-time="2026-02-25T09:00:00Z" --end-time="2026-02-25T10:00:00Z" --format="table(level,execution_id,time_utc,log)" 2>&1
```

## 分析のポイント

### ログの構造

NotiGenieのログは以下の流れで出力されます：

1. `[LINE_RECEIVED]` — LINEからのメッセージ受信
2. `[INPUT]` — ユースケースへの入力（user_utterance, session_id, date）
3. `[TURN N/M]` — Gemini AIのツール呼び出しループ
4. `[TOOL_GEN_INPUT]` / `[TOOL_GEN_OUTPUT]` — ツール生成の入出力
5. `[RESPONSE]` — 最終応答テキスト
6. `Updated history for session ...` — セッション履歴の保存

### よくあるエラーパターン

| エラー                            | 原因                                 | 対処                                                      |
| --------------------------------- | ------------------------------------ | --------------------------------------------------------- |
| `Uncaught signal: 6` + `mutex.cc` | gRPCのmutex競合（async_to_sync起因） | インスタンス再起動で自動復旧。根本対策はasync_to_sync除去 |
| `InvalidSignatureError`           | LINE署名検証失敗                     | チャネルシークレットの設定確認                            |
| `Initialization Error`            | コールドスタート時の初期化失敗       | 環境変数・APIキーの確認                                   |
| HTTP 503 + `malformed response`   | プロセスクラッシュまたはタイムアウト | ログで前後のエラーを確認                                  |
| `Invalid JWT Signature`           | Firestore認証エラー                  | サービスアカウントキーの更新                              |

### ログの日本語が文字化けしている場合

GCPのCloud Loggingに保存されるstderrログでは日本語が `?????` のように文字化けすることがあります。
これはCloud Run上のPythonのstderr出力のエンコーディング問題です。
`execution_id` 付きのログや `spanId` のあるログで処理を追跡してください。

## 注意事項

- `gcloud` CLIが認証済みであること (`gcloud auth login`)
- プロジェクトが設定済みであること (`gcloud config set project notigenie`)
- JSON形式で取得した場合は `view_file` でログファイルを読み取って分析する
- ログの `instanceId` を見ると、同一インスタンスでの処理かどうか判別できる
- `execution_id` を見ると、同一リクエストのログをグループ化できる

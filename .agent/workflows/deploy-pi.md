---
description: ローカルでDockerビルドをテストしてからRaspberry Piにデプロイ
---

# ローカル Docker ビルド & デプロイ ワークフロー

// turbo-all

## 1. ローカルでテストを実行

```bash
cd raspberry_pi
pip install pytest pytest-mock
pytest tests/ -v
```

## 2. ローカルで Docker イメージをビルド（構文エラーチェック）

```bash
cd raspberry_pi
docker compose build --no-cache client
```

> **Note**: Windows では ARM バイナリの実行テストはできないため、ビルドが成功することだけを確認します。

## 3. Raspberry Pi にデプロイ

ファイルを Raspberry Pi に転送:

```bash
scp -r raspberry_pi/* takumomo@172.16.64.50:~/notigenie-client/
```

## 4. Raspberry Pi で Docker を再ビルド & 再起動

```bash
ssh takumomo@172.16.64.50 "cd ~/notigenie-client && docker compose down && docker compose build --no-cache && docker compose up -d"
```

## 5. ログを確認

```bash
scripts/fetch_pi_logs.ps1
```

---

## トラブルシューティング

- **Python バージョンエラー**: Dockerfile の `FROM python:3.10-slim` を確認
- **AquesTalk 辞書エラー (200/154)**: `bin64/aq_dic` シンボリックリンクを確認
- **型ヒントエラー**: Python 3.10+ の構文 (`str | None`) を使用可能

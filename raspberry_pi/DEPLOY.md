# NotiGenie Raspberry Pi Deployment Guide

このガイドでは、NotiGenieのクライアントアプリをRaspberry Pi 3にデプロイし、自動起動するように設定する手順を説明します。

## 前提条件

- **Raspberry Pi 3 以上**
- **OS**: **Raspberry Pi OS (64-bit)**
  - **重要**: 32-bit版では今回のDocker構成が動作しません。必ず64-bit版をインストールしてください。
  - Raspberry Pi Imager で `Raspberry Pi OS (other)` -> `Raspberry Pi OS (64-bit)` を選択。
- インターネット接続
- SSH接続が可能であること

## 1. SSH設定と接続

### 初回セットアップ (Raspberry Pi Imager設定)

OSインストール時の設定画面（歯車アイコン）で以下を行うと便利です。

- **ホスト名**: `raspberrypi.local` (デフォルト) または任意の名前
- **SSHを有効にする**: 「公開鍵認証のみを許可する」がセキュリティ上推奨ですが、手軽さを優先するなら「パスワード認証」でも構いません。
  - **パスワード認証**: 手軽ですが、毎回入力が必要です。
  - **公開鍵認証**: 安全で、後の自動化も楽です。PCに公開鍵 (`id_rsa.pub`等) があればその中身を貼り付けます。

### 便利な接続スクリプト

PCから簡単に接続するためのスクリプトを用意しました。

```powershell
./scripts/connect_pi.ps1
```

初回実行時にSSHキーが無い場合は自動生成し、Raspberry Piへの転送コマンドを表示します（パスワード認証の場合）。

## 2. Dockerのインストール

SSHでRaspberry Piに接続し、以下のコマンドを実行してDockerをインストールしてください。
(64-bit OSであれば公式スクリプトが問題なく動作します)

```bash
# Dockerのインストールスクリプトをダウンロードして実行
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 現在のユーザー(pi)をdockerグループに追加（sudoなしでdockerコマンドを使えるようにする）
sudo usermod -aG docker $USER

# 設定を反映させるために一度ログアウトして再ログインするか、以下を実行
newgrp docker
```

正常にインストールされたか確認します:

```bash
docker --version
docker compose version
```

## 2. ファイルの転送

PCからRaspberry Piへ、`raspberry_pi` ディレクトリの内容を転送します。
SSH接続ができているPCのターミナル（PowerShellなど）から実行します。

**例:** (Raspberry PiのIPが `192.168.1.10`、ユーザー名が `pi` の場合)

```powershell
# NotiGenieプロジェクトのルートディレクトリにいる状態で実行
scp -r raspberry_pi pi@192.168.1.10:~/notigenie-client
```

## 3. 環境設定

Raspberry PiにSSH接続し、転送したディレクトリに移動します。

```bash
cd ~/notigenie-client
```

`.env` ファイルを作成し、必要なAPIキーを設定します。

```bash
nano .env
```

以下の内容を記述・編集して保存します（`Ctrl+O`, `Enter`, `Ctrl+X` で保存終了）。

```env
# Google Cloud FunctionsのURL (デプロイ済みのもの)
CLOUD_FUNCTIONS_URL=https://YOUR_REGION-YOUR_PROJECT.cloudfunctions.net/genie_entry_point

# Picovoice Access Key (https://console.picovoice.ai/ から取得)
PICOVOICE_ACCESS_KEY=your_picovoice_access_key_here

# NotiGenie API Key (Cloud Functionsで設定したものと同じ値)
NOTIGENIE_API_KEY=your_secure_api_key_here
```

## 4. 起動と自動再起動の設定

Docker Composeを使ってアプリを起動します。`docker-compose.yml` には `restart: always` 設定が含まれているため、Raspberry Piを再起動しても自動的にアプリが立ち上がります。

```bash
docker compose up -d
```

### 正常動作の確認

```bash
docker compose ps
```

`client` と `voicevox_core` のStateが `Up` になっていれば成功です。

ログを確認するには:

```bash
docker compose logs -f client
```

マイクに向かって話しかけて動作を確認してください。

```bash
# ファイル配置後
docker compose restart client
```

## 運用上の注意（重要）

### シャットダウン・再起動時の注意

- **コンテナの永続化**: 本アプリは `docker-compose.yml` 内で `restart: always` が設定されています。そのため、ラズパイ本体を再起動（`sudo reboot`）や、一度電源を切ってから再投入（シャットダウン後の起動）した場合、自動的に NotiGenie が立ち上がります。
- **やってはいけないこと**: `docker compose down` を実行して終了すると、**コンテナ自体が削除される**ため、次回のラズパイ起動時に自動実行されません。
- **推奨される終了方法**: メンテナンス等で一時的に止めたい場合は `docker compose stop` を使用してください。ラズパイ自体を終了させる場合は、そのまま `sudo shutdown -h now` を実行して問題ありません。

### 起動していない場合の確認

もしラズパイを起動しても E-Paper が更新されない、または反応がない場合は、SSH で接続して以下のコマンドを実行してください：

```bash
cd ~/notigenie-client
docker compose ps
```

もし STATUS が `Up` でない、または一覧に何も表示されない場合は、以下のコマンドで再生成・起動してください：

```bash
docker compose up -d
```

## トラブルシューティング

- **Voicevoxが起動しない**: Raspberry Pi (ARM) 用のDockerイメージが見つからない場合、ビルドが必要になることがあります。その場合はエラーログを確認してください。
- **マイクを認識しない**: ホストのオーディオデバイスをマウントしています。`docker-compose.yml` の `devices` セクションを確認してください。また、Raspberry Pi上で `arecord -l` を実行してマイクが認識されているか確認してください。

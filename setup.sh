#!/bin/bash
set -e

echo "NotiGenie 環境セットアップを開始します..."

# 1. システム依存関係のインストール
# Raspberry Pi (Audio) 用の portaudio19-dev など
echo "システム依存パッケージを更新・インストールしています..."
if command -v sudo &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y portaudio19-dev build-essential python3-dev
else
    echo "'sudo' コマンドが見つかりません。apt-get によるインストールをスキップします。"
    echo "以下のパッケージがインストールされていることを確認してください: portaudio19-dev, build-essential, python3-dev"
fi

# 2. Python 依存関係のインストール

echo "pip をアップグレードしています..."
python3 -m pip install --upgrade pip

echo "Cloud Functions の依存関係をインストールしています..."
pip install -r cloud_functions/requirements.txt

echo "テスト・開発用の依存関係をインストールしています..."
# AGENTS.md に基づく
pip install --no-cache-dir -U pytest pytest-asyncio pytest-mock flake8

echo "Raspberry Pi の依存関係をインストールしています..."
# 環境によっては一部のパッケージ（pvporcupine等）のインストールに失敗する可能性があるため、エラーを許容して続行します。
if pip install -r raspberry_pi/requirements.txt; then
    echo "Raspberry Pi の依存関係のインストールに成功しました。"
else
    echo "警告: Raspberry Pi の依存関係の一部をインストールできませんでした。"
    echo "これは、Raspberry Pi 以外の環境や、特定のオーディオドライバが不足している場合に発生することがあります。"
    echo "セットアップを続行します..."
fi

echo "セットアップが完了しました！"

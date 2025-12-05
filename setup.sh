#!/bin/bash
set -e

# 最適化: 非対話モードの設定
export DEBIAN_FRONTEND=noninteractive

echo "NotiGenie 環境セットアップ（最適化版）を開始します..."

# 1. システム依存関係のインストール
echo "システム依存パッケージを更新・インストールしています..."
if command -v sudo &> /dev/null; then
    sudo apt-get update
    # portaudio19-dev: 音声ライブラリ用
    # build-essential, python3-dev: C拡張モジュールのビルド用
    sudo apt-get install -y portaudio19-dev build-essential python3-dev

    # 最適化: apt キャッシュを削除してスナップショットサイズを削減
    echo "apt キャッシュをクリアしています..."
    sudo apt-get clean
    sudo rm -rf /var/lib/apt/lists/*
else
    echo "'sudo' コマンドが見つかりません。apt-get によるインストールをスキップします。"
    echo "注意: 必要なシステムパッケージが不足している可能性があります。"
fi

# 2. Python 依存関係のインストール

echo "pip をアップグレードしています..."
python3 -m pip install --upgrade pip

echo "Cloud Functions の依存関係をインストールしています..."
pip install -r cloud_functions/requirements.txt

echo "テスト・開発用の依存関係をインストールしています..."
# AGENTS.md に基づく
pip install pytest pytest-asyncio pytest-mock flake8

echo "Raspberry Pi の依存関係をインストールしています..."
# 環境によっては一部のパッケージ（pvporcupine等）のインストールに失敗する可能性があるため、エラーを許容して続行します。
# set -e が有効でも、if文の条件式内であればスクリプトは停止しません。
if pip install -r raspberry_pi/requirements.txt; then
    echo "Raspberry Pi の依存関係のインストールに成功しました。"
else
    echo "警告: Raspberry Pi の依存関係の一部をインストールできませんでした。"
    echo "これは、Raspberry Pi 以外の環境や、特定のオーディオドライバが不足している場合に発生することがあります。"
    echo "セットアップを続行します..."
fi

# 最適化: pip キャッシュを削除してスナップショットサイズを削減
echo "pip キャッシュをクリアしています..."
pip cache purge

echo "セットアップが完了しました！"

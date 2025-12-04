import pytest
import os
import sys

# テスト対象のモジュールをインポートするためにパスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../cloud_functions'))

def test_main_import():
    """
    cloud_functions/main.py がインポート可能かを確認するテスト。
    依存関係の欠落や構文エラー、パスの問題があればここで失敗する。
    """
    try:
        from cloud_functions import main
        assert main.main is not None
    except ImportError as e:
        pytest.fail(f"Failed to import main module: {e}")
    except Exception as e:
        pytest.fail(f"An error occurred during import: {e}")

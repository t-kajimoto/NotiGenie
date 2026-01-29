"""
NotiGenie 共通ロギング設定

全モジュールで一貫したロギング設定を提供します。
"""
import logging
import sys


def setup_logger(name: str) -> logging.Logger:
    """
    指定された名前でロガーを作成し、標準設定を適用します。

    Args:
        name (str): ロガー名（通常は __name__）

    Returns:
        logging.Logger: 設定済みのロガー
    """
    logger = logging.getLogger(name)
    
    # 既に設定済みの場合はそのまま返す
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)
    
    return logger

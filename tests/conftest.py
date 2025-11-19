import sys
import os

# srcディレクトリをパスに追加して、テストからプロダクトコードをインポートできるようにする
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

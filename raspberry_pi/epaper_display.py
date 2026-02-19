import argparse
import json
import logging
import os
import sys
import time
import requests
from datetime import datetime, timezone, timedelta

# 日本標準時 (UTC+9)
JST = timezone(timedelta(hours=9))
from PIL import Image, ImageDraw, ImageFont

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cloud Functions API URL (環境変数で設定するか、引数で渡す)
API_URL_DEFAULT = "https://asia-northeast1-YOUR-PROJECT-ID.cloudfunctions.net/notigenie/api/todo_list"
API_KEY_ENV = "NOTIGENIE_API_KEY"

# フォント設定: NotoSansCJK を最優先で使用
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",   # Docker (fonts-noto-cjk)
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",       # Raspberry Pi OS
]
# Mac/Windows開発用フォールバック
if sys.platform == "darwin":
    FONT_CANDIDATES.append("/System/Library/Fonts/Hiragino Sans GB.ttc")
elif sys.platform == "win32":
    FONT_CANDIDATES.append("C:\\Windows\\Fonts\\msgothic.ttc")

FONT_PATH = None
for candidate in FONT_CANDIDATES:
    if os.path.exists(candidate):
        FONT_PATH = candidate
        break

if not FONT_PATH:
    logger.warning("No Japanese font found. Text may not render correctly.")

# Sample Data for Mock/Testing
SAMPLE_DATA = {
    "query_date": "2026-01-30",
    "todos": [
        {
            "name": "謎解きデートに行く",
            "deadline": "2026-02-28",
            "display_date": "2月中",
            "memo": "地下謎への招待状2026 (開催中) http://example.com/very/long/url..."
        },
        {
            "name": "部屋の掃除",
            "deadline": "2026-01-31",
            "display_date": "今週中",
            "memo": ""
        },
        {
            "name": "牛乳を買う",
            "deadline": "2026-01-30",
            "display_date": "今日",
            "memo": "低脂肪乳"
        }
    ],
    "dones": [
        {
            "name": "燃えるゴミ出し",
            "done_date": "2026-01-30"
        },
        {
            "name": "銀行振込",
            "done_date": "2026-01-29"
        }
    ]
}

def get_todo_data(api_url, api_key):
    """APIからToDoデータを取得する"""
    headers = {"X-API-Key": api_key}
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch data: {e}")
        return None

def _truncate_by_pixel(draw, text, font, max_width):
    """
    テキストをピクセル幅で切り詰める。
    描画幅がmax_widthを超える場合、末尾を「...」に置き換えて収まるようにする。
    """
    # テキストがそのまま収まるならそのまま返す
    try:
        text_width = draw.textlength(text, font=font)
    except AttributeError:
        # Pillow < 8.0 互換: textsize を使用
        text_width = draw.textsize(text, font=font)[0]

    if text_width <= max_width:
        return text

    # 1文字ずつ削って「...」を付けて収まるか確認
    ellipsis = "..."
    for i in range(len(text), 0, -1):
        truncated = text[:i] + ellipsis
        try:
            w = draw.textlength(truncated, font=font)
        except AttributeError:
            w = draw.textsize(truncated, font=font)[0]
        if w <= max_width:
            return truncated

    return ellipsis


def draw_todo_list(data, width=480, height=800):
    """
    ToDoリストを画像に描画する (縦向き 480x800)
    
    レイアウト戦略:
    1. まず「最近の完了」セクションの必要高さを計算（下部に最低限のスペース）
    2. 残りのスペースを全て未完了タスクに割り当てる
    3. 完了タスクがなければ「なし」と表示
    """
    image = Image.new('1', (width, height), 255)  # 1-bit白黒
    draw = ImageDraw.Draw(image)

    try:
        font_header = ImageFont.truetype(FONT_PATH, 40)
        font_title = ImageFont.truetype(FONT_PATH, 28)
        font_detail = ImageFont.truetype(FONT_PATH, 20)
        font_done = ImageFont.truetype(FONT_PATH, 18)
    except Exception as e:
        logger.warning(f"Font load error: {e}. Using default font.")
        font_header = ImageFont.load_default()
        font_title = ImageFont.load_default()
        font_detail = ImageFont.load_default()
        font_done = ImageFont.load_default()

    # =========================================================
    # Step 1: 「最近の完了」セクションの必要高さを先に計算
    # =========================================================
    dones = data.get("dones", [])
    # ヘッダー行 + 区切り線のスペース
    done_section_height = 60  # ヘッダー(40px) + マージン(20px)
    if dones:
        # 各完了タスクの行数分 (1行25px)
        done_section_height += len(dones) * 25 + 10  # +下マージン
    else:
        # 「なし」の1行分
        done_section_height += 30

    # 完了セクションの開始Y座標（画面下部から計算）
    done_section_y = height - done_section_height

    # 未完了タスクが使える最大Y座標（完了セクションの上 - マージン）
    todo_max_y = done_section_y - 20

    # =========================================================
    # Step 2: ヘッダー (日付) 描画
    # =========================================================
    current_date = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    draw.text((10, 10), f"NotiGenie TODO  {current_date}", font=font_detail, fill=0)
    draw.line((10, 40, width-10, 40), fill=0)

    y = 50

    # =========================================================
    # Step 3: 未完了タスク描画（利用可能なスペースを全て使う）
    # =========================================================
    draw.text((10, y), "【TODO】", font=font_header, fill=0)
    y += 50
    
    todos = data.get("todos", [])
    if not todos:
        draw.text((30, y), "なし", font=font_title, fill=0)
        y += 40
    
    for todo in todos:
        # タスク名
        name = todo.get("name", "")
        chk_mark = "□"
        draw.text((20, y), f"{chk_mark} {name}", font=font_title, fill=0)
        y += 35
        
        # 期限・メモ情報
        deadline = todo.get("deadline", "")
        display_date = todo.get("display_date", "")
        memo = todo.get("memo", "")
        
        info_text = ""
        if display_date:
            info_text += f"[期限: {display_date}] "
        elif deadline:
            info_text += f"[期限: {deadline}] "
            
        if memo:
            # 改行を半角スペースに置換して1行にまとめる
            memo = memo.replace("\n", " ").replace("\r", " ").strip()
            info_text += memo
            
        if info_text:
            # ピクセル幅ベースで切り詰め（画面幅 - 左右マージン）
            max_text_width = width - 60  # 左50px + 右10px
            info_text = _truncate_by_pixel(draw, info_text, font_detail, max_text_width)            
            draw.text((50, y), info_text, font=font_detail, fill=0)
            y += 30
        
        y += 10  # タスク間のスペーサー

        # 完了セクション手前で打ち切り
        if y > todo_max_y:
            break

    # =========================================================
    # Step 4: 「最近の完了」セクション描画（下部に最低限のスペース）
    # =========================================================
    y = done_section_y
    draw.line((10, y - 5, width-10, y - 5), fill=0)
    draw.text((10, y), "【Done】", font=font_header, fill=0)
    y += 50
    
    if not dones:
        draw.text((30, y), "なし", font=font_done, fill=0)
    else:
        for done in dones:
            name = done.get("name", "")
            date = done.get("done_date", "")
            draw.text((20, y), f"■ {name} ({date})", font=font_done, fill=0)
            y += 25
            if y > height - 10:
                break

    return image

def main():
    parser = argparse.ArgumentParser(description="E-paper Display Client for NotiGenie")
    parser.add_argument("--api-url", default=API_URL_DEFAULT, help="Cloud Functions API URL")
    parser.add_argument("--api-key", help="API Key (or use env NOTIGENIE_API_KEY)")
    parser.add_argument("--mock", action="store_true", help="Run correctly without E-paper hardware (save image to disk)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get(API_KEY_ENV)
    
    # 1. データ取得
    if args.mock:
        logger.info("Mock mode: Using SAMPLE_DATA")
        data = SAMPLE_DATA
    else:
        if not api_key:
            logger.error("API Key is required. Set NOTIGENIE_API_KEY env or use --api-key.")
            return

        logger.info("Fetching data...")
        data = get_todo_data(args.api_url, api_key)
        if not data:
            logger.error("No data received.")
            return

    # 2. 画像生成
    logger.info("Generating image...")
    image = draw_todo_list(data)

    # 3. 表示更新
    if args.mock:
        logger.info("Mock mode: Saving image to 'epaper_output.png'")
        image.save("epaper_output.png")
    else:
        try:
            logger.info("Initializing E-paper...")
            try:
                from waveshare_epaper import epd7in5_V2
            except ImportError:
                # Fallback for compatibility or if installed differently
                from waveshare_epd import epd7in5_V2
            epd = epd7in5_V2.EPD()
            
            logger.info("Clear...")
            epd.init()
            epd.Clear()
            
            logger.info("Displaying...")
            # E-paperライブラリは通常、Pillow imageを受け取る
            # 回転が必要な場合はここで image.rotate() する
            # 7.5inch (800x480) は横長がネイティブの場合が多いので、
            # 縦向き(480x800)で作った画像を回転させる必要があるかもしれない
            # ここではハードウェア仕様に合わせて適宜調整
            # 仮にネイティブが横(800x480)だとして、縦(480x800)の画像を90度回転させる
            # image_rotated = image.rotate(90, expand=True) 
            # epd.display(epd.getbuffer(image_rotated))
            
            # 今回は仕様書に合わせて縦(480x800)で生成しているので、そのままバッファ変換して渡す
            # 実際にはドライバの実装と実機の向きによる
            
            epd.display(epd.getbuffer(image))
            
            logger.info("Sleeping...")
            epd.sleep()
            
        except ImportError:
            logger.error("waveshare_epd library not found. Use --mock to run on PC.")
        except Exception as e:
            logger.error(f"E-paper error: {e}")

if __name__ == "__main__":
    main()

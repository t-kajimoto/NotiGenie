import time
import asyncio

# --------------------------------------------------------------------------
# 1. ライブラリのインポートと互換性確保
# --------------------------------------------------------------------------
try:
    import RPi.GPIO as GPIO
    IS_RASPBERRY_PI = True
except (RuntimeError, ModuleNotFoundError):
    print("RPi.GPIOライブラリが見つかりません。ダミーモードで実行します。")
    IS_RASPBERRY_PI = False

# --------------------------------------------------------------------------
# 2. ダミーGPIOクラスの定義
# --------------------------------------------------------------------------
class MockGPIO:
    BCM = "BCM"
    IN = "IN"
    PUD_UP = "PUD_UP"
    FALLING = "FALLING"

    def setmode(self, mode):
        print(f"[DUMMY] GPIO mode set to {mode}")

    def setup(self, pin, direction, pull_up_down=None):
        print(f"[DUMMY] Pin {pin} setup as {direction} with pull-up/down {pull_up_down}")

    def add_event_detect(self, pin, edge, callback, bouncetime):
        print(f"[DUMMY] Event detection added for pin {pin} on edge {edge} with bouncetime {bouncetime}")
        if not IS_RASPBERRY_PI:
            import threading
            self._dummy_input_thread = threading.Thread(target=self._wait_for_enter, args=(callback, pin))
            self._dummy_input_thread.daemon = True
            self._dummy_input_thread.start()

    def _wait_for_enter(self, callback, pin):
        print("（ダミーモードです。Enterキーを押すと、ボタンが押されたことをシミュレートします）")
        try:
            input() # Enterキーが押されるのを待つ
            callback(pin) # 擬似的にコールバックを呼び出す
        except EOFError:
            pass
        except Exception as e:
            print(f"ダミー入力スレッドでエラーが発生しました: {e}")

    def cleanup(self):
        print("[DUMMY] GPIO cleanup called")

if not IS_RASPBERRY_PI:
    GPIO = MockGPIO()

# --------------------------------------------------------------------------
# 3. ButtonHandlerクラスの定義
# --------------------------------------------------------------------------
class ButtonHandler:
    """
    物理ボタンの押下を検知し、登録された処理（コールバック）を実行する責務を持つクラス。
    """
    def __init__(self, button_pin=17, bouncetime=300):
        self.button_pin = button_pin
        self.bouncetime = bouncetime
        self._button_press_callback = None
        try:
            # メインスレッドで実行されているイベントループを取得
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            # mainがasyncでない場合など、実行中のループがない場合に発生
            print("警告: 実行中のイベントループが見つかりません。新しいループを作成します。")
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def set_button_press_callback(self, callback):
        """
        ボタンが押されたときに実行したい関数（コールバック関数）を外部から登録するためのメソッド。
        """
        self._button_press_callback = callback
        GPIO.add_event_detect(
            self.button_pin, 
            GPIO.FALLING, 
            callback=self._internal_callback, 
            bouncetime=self.bouncetime
        )

    def _internal_callback(self, channel):
        """
        GPIOライブラリによって直接呼び出される内部用のコールバック。
        """
        if self._button_press_callback and self.loop:
            print(f"ボタンがピン{channel}で検知されました。登録されたコールバックを呼び出します。")
            if asyncio.iscoroutinefunction(self._button_press_callback):
                # 別スレッドからメインスレッドのイベントループにコルーチンを安全に投入
                asyncio.run_coroutine_threadsafe(self._button_press_callback(), self.loop)
            else:
                # 同期コールバックの場合は、ループにコールバックをスケジュールする
                self.loop.call_soon_threadsafe(self._button_press_callback)

    def cleanup(self):
        """
        スクリプト終了時に、使用したGPIOピンの設定をリセットするためのメソッド。
        """
        GPIO.cleanup()

# --------------------------------------------------------------------------
# 4. 動作確認用のサンプルコード
# --------------------------------------------------------------------------
def sample_callback():
    print("----------------------------------------")
    print("  コールバックが実行されました！")
    print("----------------------------------------")

async def main_async():
    print("物理ボタン検知スクリプト（非同期）を開始します。Ctrl+Cで終了します。")
    button_handler = ButtonHandler()
    button_handler.set_button_press_callback(sample_callback)
    print(f"ピン{button_handler.button_pin}のボタン押下を待っています...")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nプログラムを終了します。")
    finally:
        button_handler.cleanup()

if __name__ == '__main__':
    asyncio.run(main_async())

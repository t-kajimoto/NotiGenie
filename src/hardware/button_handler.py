import time

# --------------------------------------------------------------------------
# 1. ライブラリのインポートと互換性確保
# --------------------------------------------------------------------------
# Raspberry Pi以外の環境（WindowsやMacなど）で開発する際、
# ハードウェアを直接操作するRPi.GPIOライブラリは存在しないため、
# `import RPi.GPIO`の行でエラー（RuntimeErrorやModuleNotFoundError）が発生します。
# このtry-except構文は、そのエラーをあえてキャッチすることで、
# スクリプトが強制終了するのを防ぎ、開発環境でも動作させるための仕組みです。
try:
    # まず、Raspberry Pi環境でのみ成功するライブラリのインポートを試みます。
    import RPi.GPIO as GPIO
    # インポートが成功した場合、IS_RASPBERRY_PIフラグをTrueに設定します。
    IS_RASPBERRY_PI = True
except (RuntimeError, ModuleNotFoundError):
    # インポートに失敗した場合（＝Raspberry Pi以外の環境の場合）、
    # ダミーモードで動作することをユーザーに通知し、フラグをFalseに設定します。
    print("RPi.GPIOライブラリが見つかりません。ダミーモードで実行します。")
    IS_RASPBERRY_PI = False

# --------------------------------------------------------------------------
# 2. ダミーGPIOクラスの定義
# --------------------------------------------------------------------------
# Raspberry Pi以外の環境で、RPi.GPIOの代わりとして振る舞う「ダミー」のクラスです。
# 本物のRPi.GPIOライブラリと同じ名前のメソッド（関数）を持っていますが、
# 実際にはハードウェアを操作せず、何が実行されようとしているかをコンソールに表示するだけです。
# これにより、ハードウェアに依存する部分のコードを書き換えることなく、
# 他のPCでもアプリケーションのロジック部分の開発やテストが可能になります。
class MockGPIO:
    # RPi.GPIOで定義されている定数を模倣
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
        # ダミーモードでは、別スレッドでEnterキー入力を待ち受ける
        if not IS_RASPBERRY_PI:
            import threading
            self._dummy_input_thread = threading.Thread(target=self._wait_for_enter, args=(callback, pin))
            self._dummy_input_thread.daemon = True # メインスレッド終了時に一緒に終了
            self._dummy_input_thread.start()

    def _wait_for_enter(self, callback, pin):
        print("（ダミーモードです。Enterキーを押すと、ボタンが押されたことをシミュレートします）")
        try:
            input() # Enterキーが押されるのを待つ
            callback(pin) # 擬似的にコールバックを呼び出す
        except EOFError:
            # 非対話型実行の場合、EOFErrorが発生するので無視する
            pass
        except Exception as e:
            print(f"ダミー入力スレッドでエラーが発生しました: {e}")

    def cleanup(self):
        print("[DUMMY] GPIO cleanup called")

# IS_RASPBERRY_PIフラグがFalseの場合、
# グローバル変数`GPIO`に、本物のRPi.GPIOの代わりにダミークラスのインスタンスを代入します。
# これ以降、コード内で`GPIO.setmode()`などを呼び出すと、ダミーのメソッドが実行されるようになります。
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
        """
        コンストラクタ：ButtonHandlerが生成されるときに最初に呼ばれる関数。

        Args:
            button_pin (int): ボタンが接続されているGPIOピンの番号（BCMモード）。
            bouncetime (int): チャタリング防止の時間（ミリ秒）。
                              物理ボタンは押した瞬間に微細な振動でON/OFFを繰り返すため、
                              一度の押下を複数回として検知しないように待機時間を設ける。
        """
        self.button_pin = button_pin
        self.bouncetime = bouncetime
        self._button_press_callback = None # 押されたときに実行する関数を保持する変数

        # GPIOピンのモードをBCM（Broadcom SOC channel）番号で指定する設定。
        GPIO.setmode(GPIO.BCM)
        # 指定されたピンを入力モードに設定し、内部プルアップ抵抗を有効にする。
        # プルアップ抵抗を有効にすると、ボタンが押されていない状態ではピンがHIGH(高電圧)になり、
        # ボタンが押されるとGND(0V)に接続されてLOW(低電圧)になる。
        GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def set_button_press_callback(self, callback):
        """
        ボタンが押されたときに実行したい関数（コールバック関数）を外部から登録するためのメソッド。
        """
        self._button_press_callback = callback
        # GPIOピンの電圧がHIGHからLOWに変わる瞬間（FALLINGエッジ）を監視するイベントを設定。
        # このイベントが発生すると、`_internal_callback`メソッドが呼び出される。
        GPIO.add_event_detect(
            self.button_pin, 
            GPIO.FALLING, 
            callback=self._internal_callback, 
            bouncetime=self.bouncetime
        )

    def _internal_callback(self, channel):
        """
        GPIOライブラリによって直接呼び出される内部用のコールバック。
        channel引数には、イベントが発生したピン番号が渡される。
        """
        # コールバック関数が登録されていれば実行する。
        if self._button_press_callback:
            print(f"ボタンがピン{channel}で検知されました。登録されたコールバックを呼び出します。")
            self._button_press_callback()

    def cleanup(self):
        """
        スクリプト終了時に、使用したGPIOピンの設定をリセットするためのメソッド。
        """
        GPIO.cleanup()

# --------------------------------------------------------------------------
# 4. 動作確認用のサンプルコード
# --------------------------------------------------------------------------
# このスクリプトが直接 `python button_handler.py` のように実行された場合にのみ、
# 以下のコードブロックが実行される。他のファイルから`import`された場合は実行されない。
def sample_callback():
    """
    ボタンが押されたときに実行されるサンプル関数。
    """
    print("----------------------------------------")
    print("  コールバックが実行されました！")
    print("  ここに、録音開始などの処理を記述します。")
    print("----------------------------------------")

if __name__ == '__main__':
    print("物理ボタン検知スクリプトを開始します。Ctrl+Cで終了します。")

    # ButtonHandlerクラスのインスタンスを作成（ピン17番を使用）
    button_handler = ButtonHandler(button_pin=17)

    # 作成したサンプル関数をコールバックとして登録
    button_handler.set_button_press_callback(sample_callback)

    print(f"ピン{button_handler.button_pin}のボタン押下を待っています...")

    

    try:
        # スクリプトがすぐに終了してしまわないように、無限ループで待機する。
        # ユーザーがCtrl+Cを押すまで、プログラムはここで待ち続ける。
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Ctrl+Cが押されたらループを抜け、終了メッセージを表示する。
        print("\nプログラムを終了します。")
    finally:
        # プログラムが終了する前に、必ずGPIOのクリーンアップ処理を呼び出す。
        button_handler.cleanup()
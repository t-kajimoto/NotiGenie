"""
AquesTalk Pi TTS Client

「ゆっくりボイス」で知られる軽量なTTSエンジン。
Raspberry Pi 3でもリアルタイム発話が可能。
"""
import os
import subprocess
import re
from typing import Optional

from tts_interface import TTSClient


class AquesTalkClient(TTSClient):
    """AquesTalk Pi を使用したTTSクライアント"""

    def __init__(self, voice_type: str = "f1"):
        """
        Args:
            voice_type: 声の種類 (f1=女性1, f2=女性2, m1=男性1, m2=男性2, r1=ロボット)
        """
        self.voice_type = voice_type
        # AquesTalk Pi のインストールディレクトリ (aq_dic がある場所)
        self.aquestalk_dir = os.getenv("AQUESTALK_DIR", "/app/aquestalk/aquestalkpi")
        # 32-bit binary path (root of aquestalk_dir)
        # Using 32-bit version via multiarch (armhf) to avoid 48-bit VA issues on Pi 5/3(64bit)
        self.aquestalk_bin = os.path.join(self.aquestalk_dir, "AquesTalkPi")
        self.output_device_index = self._get_output_device_card_index()
        print(f"AquesTalkClient initialized (voice: {voice_type})")

    def _get_output_device_card_index(self) -> Optional[str]:
        """
        Finds the ALSA card index for the USB Audio device using 'aplay -l'.
        Returns the card number (e.g., '2') as a string, or None.
        """
        try:
            result = subprocess.check_output(["aplay", "-l"], text=True)
            match = re.search(r'card\s+(\d+):.*USB.*Audio', result, re.IGNORECASE)
            if match:
                card_index = match.group(1)
                print(f"Found USB Audio Device at ALSA card {card_index}")
                return card_index
        except Exception as e:
            print(f"Error finding audio device using aplay -l: {e}")

        print("USB Audio device not found via aplay -l. Using default.")
        return None

    def speak(self, text: str) -> None:
        """
        テキストを音声に変換して再生する。

        AquesTalk Pi はテキストを標準入力から受け取り、WAV形式の音声を標準出力に出力する。
        これをaplayにパイプして再生する。
        """
        import time
        t0 = time.perf_counter()

        try:
            # AquesTalk Pi コマンド
            # -v: 声の種類, -s: 速度, -f -: ファイル入力(標準入力)
            aquestalk_cmd = [self.aquestalk_bin, "-v", self.voice_type, "-f", "-"]

            # aplay コマンド
            aplay_cmd = ["aplay", "-q"]
            if self.output_device_index:
                device_name = f"plughw:{self.output_device_index},0"
                aplay_cmd.extend(["-D", device_name])

            print(f"Speaking: {text[:30]}...")
            
            # AquesTalk Pi を起動 (stdin=PIPE, stdout=PIPE)
            # cwd を aquestalk_dir に設定 (辞書ロードのため)
            aquestalk_proc = subprocess.Popen(
                aquestalk_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.aquestalk_dir
            )

            # aplay を起動 (stdin=aquestalk_proc.stdout)
            # これにより Python を介さずに直接カーネルバッファ経由でデータが流れる (ストリーム再生)
            aplay_proc = subprocess.Popen(
                aplay_cmd,
                stdin=aquestalk_proc.stdout,
                stdout=subprocess.DEVNULL, # aplayの出力は捨てる
                stderr=subprocess.PIPE
            )

            # テキストを送信
            # communicate() は stdout を読み込んでしまうため、stdin.write() を使用
            try:
                aquestalk_proc.stdin.write(text.encode('utf-8'))
                aquestalk_proc.stdin.close() # EOFを送る
            except Exception as e:
                print(f"Error writing to AquesTalk inputs: {e}")
                aquestalk_proc.kill()
                aplay_proc.kill()
                return

            # プロセスの終了を待機
            # aplay が再生を終えるまで待つ
            _, aplay_stderr = aplay_proc.communicate()
            aquestalk_proc.wait()

            t1 = time.perf_counter()

            if aquestalk_proc.returncode != 0:
                # エラーメッセージを取得 (stderr はまだ読めるはず)
                err = aquestalk_proc.stderr.read().decode('utf-8', errors='ignore')
                print(f"AquesTalk failed with return code {aquestalk_proc.returncode}: {err}")
            elif aplay_proc.returncode != 0:
                print(f"aplay failed: {aplay_stderr.decode('utf-8', errors='ignore')}")
            else:
                print(f"AquesTalk speak completed (streamed) in {t1-t0:.2f}s")

        except FileNotFoundError:
            print(f"Error: AquesTalk Pi not found at {self.aquestalk_bin}")
            print("Please download AquesTalk Pi from https://www.a-quest.com/products/aquestalkpi.html")
        except Exception as e:
            print(f"AquesTalk Error: {e}")




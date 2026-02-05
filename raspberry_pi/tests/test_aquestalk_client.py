"""
AquesTalkClient unit tests

AquesTalk Pi は ARM専用バイナリのため、ローカル開発環境（Windows/x86 Linux）では
実行できない。そのため、subprocess.Popen をモックして以下をテストする：
1. コマンドライン引数の正しい構築
2. 作業ディレクトリ (cwd) の正しい設定
3. テキストの stdin への正しい送信
4. エラーハンドリング
"""
import os
import pytest
from unittest.mock import patch, MagicMock


class TestAquesTalkClient:
    """AquesTalkClient のユニットテスト"""

    @pytest.fixture
    def mock_aplay_output(self):
        """aplay -l の出力をモック"""
        return """
**** List of PLAYBACK Hardware Devices ****
card 0: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
card 1: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]
card 2: Device [USB Composite Device], device 0: USB Audio [USB Audio]
"""

    @pytest.fixture
    def client(self, mock_aplay_output):
        """AquesTalkClient インスタンスを作成"""
        with patch('subprocess.check_output', return_value=mock_aplay_output):
            # tts_interface は同じディレクトリにあるのでインポート可能
            from aquestalk_client import AquesTalkClient
            return AquesTalkClient(voice_type="f1")

    def test_init_finds_usb_audio_device(self, mock_aplay_output):
        """初期化時にUSB Audioデバイスが正しく検出される"""
        with patch('subprocess.check_output', return_value=mock_aplay_output):
            from aquestalk_client import AquesTalkClient
            client = AquesTalkClient()
            assert client.output_device_index == "2"

    def test_init_default_voice_type(self, mock_aplay_output):
        """デフォルトの声種はf1"""
        with patch('subprocess.check_output', return_value=mock_aplay_output):
            from aquestalk_client import AquesTalkClient
            client = AquesTalkClient()
            assert client.voice_type == "f1"

    def test_aquestalk_binary_path(self, client):
        """AquesTalkバイナリのパスが正しく設定される"""
        # Windows/Linux 両方で動作するようにパス区切りを考慮
        assert "AquesTalkPi" in client.aquestalk_bin
        assert "bin64" in client.aquestalk_bin
        assert "aquestalk" in client.aquestalk_bin.lower()

    def test_speak_command_construction(self, client):
        """speak()が正しいコマンドを構築する"""
        with patch('subprocess.Popen') as mock_popen:
            # AquesTalk のモック
            mock_aquestalk = MagicMock()
            mock_aquestalk.returncode = 0
            mock_aquestalk.communicate.return_value = (b'RIFF' + b'\x00' * 100, b'')
            
            # aplay のモック
            mock_aplay = MagicMock()
            mock_aplay.returncode = 0
            mock_aplay.communicate.return_value = (b'', b'')
            
            mock_popen.side_effect = [mock_aquestalk, mock_aplay]
            
            client.speak("テスト")
            
            # AquesTalk コマンドの確認
            aquestalk_call = mock_popen.call_args_list[0]
            assert client.aquestalk_bin in aquestalk_call[0][0]
            assert "-v" in aquestalk_call[0][0]
            assert "f1" in aquestalk_call[0][0]

    def test_speak_cwd_is_bin_directory(self, client):
        """speak()がバイナリと同じディレクトリをcwdとして使用する"""
        with patch('subprocess.Popen') as mock_popen:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (b'RIFF' + b'\x00' * 100, b'')
            mock_popen.return_value = mock_proc
            
            client.speak("テスト")
            
            # cwd が bin64 ディレクトリであることを確認 (Windows/Linux両対応)
            aquestalk_call = mock_popen.call_args_list[0]
            cwd = aquestalk_call[1].get('cwd')
            assert cwd is not None
            assert "bin64" in cwd

    def test_speak_text_encoding(self, client):
        """speak()がテキストをUTF-8でエンコードして送信する"""
        with patch('subprocess.Popen') as mock_popen:
            mock_aquestalk = MagicMock()
            mock_aquestalk.returncode = 0
            mock_aquestalk.communicate.return_value = (b'RIFF' + b'\x00' * 100, b'')
            
            mock_aplay = MagicMock()
            mock_aplay.returncode = 0
            mock_aplay.communicate.return_value = (b'', b'')
            
            mock_popen.side_effect = [mock_aquestalk, mock_aplay]
            
            test_text = "日本語テスト"
            client.speak(test_text)
            
            # communicate に正しくエンコードされたテキストが渡されたか確認
            mock_aquestalk.communicate.assert_called_once()
            input_data = mock_aquestalk.communicate.call_args[1]['input']
            assert input_data == test_text.encode('utf-8')

    def test_speak_handles_aquestalk_error(self, client, capsys):
        """AquesTalkがエラーを返した場合のハンドリング"""
        with patch('subprocess.Popen') as mock_popen:
            mock_proc = MagicMock()
            mock_proc.returncode = 200  # 辞書エラー
            mock_proc.communicate.return_value = (b'', b'ERR: dictionary not found')
            mock_popen.return_value = mock_proc
            
            client.speak("テスト")
            
            captured = capsys.readouterr()
            assert "failed with return code 200" in captured.out

    def test_speak_handles_binary_not_found(self, client, capsys):
        """AquesTalkバイナリが見つからない場合のハンドリング"""
        with patch('subprocess.Popen', side_effect=FileNotFoundError()):
            client.speak("テスト")
            
            captured = capsys.readouterr()
            assert "not found" in captured.out.lower()

    def test_speak_aplay_device_selection(self, client):
        """aplayコマンドにUSBデバイスが指定される"""
        with patch('subprocess.Popen') as mock_popen:
            mock_aquestalk = MagicMock()
            mock_aquestalk.returncode = 0
            mock_aquestalk.communicate.return_value = (b'RIFF' + b'\x00' * 100, b'')
            
            mock_aplay = MagicMock()
            mock_aplay.returncode = 0
            mock_aplay.communicate.return_value = (b'', b'')
            
            mock_popen.side_effect = [mock_aquestalk, mock_aplay]
            
            client.speak("テスト")
            
            # aplay コマンドの確認
            aplay_call = mock_popen.call_args_list[1]
            aplay_cmd = aplay_call[0][0]
            assert "aplay" in aplay_cmd
            assert "-D" in aplay_cmd
            assert "plughw:2,0" in aplay_cmd


class TestAquesTalkClientNoDevice:
    """USBデバイスが見つからない場合のテスト"""

    def test_no_usb_device_uses_default(self):
        """USBデバイスがない場合はデフォルトを使用"""
        with patch('subprocess.check_output', return_value="no usb devices"):
            from aquestalk_client import AquesTalkClient
            client = AquesTalkClient()
            assert client.output_device_index is None

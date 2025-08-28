
from domain.use_cases.record_and_transcribe import RecordAndTranscribeUseCase

class MainController:
    """アプリケーションのメインコントローラ"""
    def __init__(self, use_case: RecordAndTranscribeUseCase):
        self.use_case = use_case

    def on_button_pressed(self):
        print("コントローラ: ボタン押下を検知しました。")
        self.use_case.execute()

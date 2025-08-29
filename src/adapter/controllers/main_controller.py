
from domain.use_cases.record_and_transcribe import RecordAndTranscribeUseCase
from domain.use_cases.interpret_and_execute import InterpretAndExecuteUseCase

class MainController:
    """アプリケーションのメインコントローラ"""
    def __init__(self, record_and_transcribe_use_case: RecordAndTranscribeUseCase, interpret_and_execute_use_case: InterpretAndExecuteUseCase):
        self.record_and_transcribe_use_case = record_and_transcribe_use_case
        self.interpret_and_execute_use_case = interpret_and_execute_use_case

    def on_button_pressed(self):
        print("コントローラ: ボタン押下を検知しました。")
        transcribed_text = self.record_and_transcribe_use_case.execute()
        if transcribed_text:
            print(f"コントローラ: 文字起こし結果: {transcribed_text}")
            final_response = self.interpret_and_execute_use_case.execute(transcribed_text)
            print(f"コントローラ: 最終応答: {final_response}")
        else:
            print("コントローラ: 文字起こしに失敗しました。")

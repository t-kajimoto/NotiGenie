import os
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートの設定
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "cloud_functions"))

from cloud_functions.core.interfaces.gateways.gemini_adapter import GeminiAdapter
from cloud_functions.core.interfaces.gateways.notion_adapter import NotionAdapter
from cloud_functions.core.interfaces.gateways.firestore_adapter import FirestoreAdapter
from cloud_functions.core.use_cases.process_message import ProcessMessageUseCase

# テスト用DB ID (conftest.py と同じ)
TEST_DB_ID = "3051ac9c-8c70-812f-9acc-e15173a81bba"
TEST_DB_SCHEMA = {
    "master_db": {
        "title": "E2Eテスト用DB",
        "id": TEST_DB_ID,
        "description": "E2Eテスト専用",
        "properties": {
            "タイトル": {"type": "title"},
            "カテゴリ": {"type": "select", "options": ["Shopping", "TODO", "Menu", "Other"]},
            "メモ": {"type": "rich_text"},
            "予定日": {"type": "date"},
            "予定日表示": {"type": "rich_text"},
            "完了日": {"type": "date"},
        },
    }
}

def setup():
    env_path = Path(__file__).parent / ".env.test"
    load_dotenv(env_path, override=True)
    
    # Check keys
    if not os.environ.get("GEMINI_API_KEY") or not os.environ.get("NOTION_API_KEY"):
        print("ERROR: API keys not found in .env.test")
        sys.exit(1)
        
    # Force set GOOGLE_APPLICATION_CREDENTIALS to absolute path
    cred_path = (Path(__file__).parent / "google-credential.json").resolve()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)
    print(f"Using Google Credentials: {cred_path}")
        
    print("Initializing adapters...")
    
    # Prompts
    prompts_dir = ROOT_DIR / "cloud_functions" / "prompts"
    system_instruction = (prompts_dir / "system_instruction.md").read_text(encoding="utf-8")
    response_instruction = (prompts_dir / "response_instruction.md").read_text(encoding="utf-8")

    # Adapters
    gemini = GeminiAdapter(system_instruction, TEST_DB_SCHEMA, response_instruction)
    notion = NotionAdapter(TEST_DB_SCHEMA)
    firestore = FirestoreAdapter()
    
    use_case = ProcessMessageUseCase(gemini, notion, firestore)
    use_case.db_schemas = TEST_DB_SCHEMA
    
    return use_case

import asyncio
from datetime import datetime

async def main():
    use_case = setup()
    session_id = f"manual-{uuid.uuid4().hex[:6]}"
    
    print("\n" + "="*60)
    print(" 🤖 NotiGenie Interactive E2E Test")
    print("="*60)
    print(f" Session ID: {session_id}")
    print(f" Target DB : https://www.notion.so/{TEST_DB_ID.replace('-', '')}")
    print(" Type 'exit' or 'quit' to end.\n")
    
    while True:
        try:
            # Note: input() is blocking, which is fine for this simple script
            user_input = input("\nYou > ")
            if user_input.lower() in ["exit", "quit"]:
                break
            if not user_input.strip():
                continue
                
            print("Bot > Thinking...")
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Execute is async and returns a string
            response = await use_case.execute(user_input, current_date, session_id)
            print(f"Bot > {response}")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\nGoodbye!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

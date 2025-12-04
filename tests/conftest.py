import sys
import os

# Set dummy env vars for testing
os.environ["GEMINI_API_KEY"] = "dummy"
os.environ["NOTION_API_KEY"] = "dummy"
os.environ["PICOVOICE_ACCESS_KEY"] = "dummy"

# Add root directory to path to allow importing cloud_functions and raspberry_pi
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

# Add cloud_functions directory to path to allow imports from core inside main.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../cloud_functions')))

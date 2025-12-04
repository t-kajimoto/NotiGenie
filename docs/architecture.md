# Architecture Documentation

## Overview
This project implements a voice-activated assistant using Raspberry Pi (client) and Google Cloud Functions (backend).
The system uses Google's Gemini LLM for natural language processing and Notion as a database for task management, shopping lists, etc.

## Core Concepts
- **Function Calling**: The backend utilizes the Gemini API's "Function Calling" (Tools) capability. Instead of parsing raw JSON from text responses, the model directly invokes Python functions (Tools) defined in the application.
- **Clean Architecture**: The Cloud Functions backend is organized into layers:
  - **Core (Domain & Use Cases)**: Business logic and interfaces.
  - **Infrastructure (Gateways)**: External API adapters (Gemini, Notion).
  - **Main**: Entry point and dependency injection.

## Backend Components (`cloud_functions/`)

### 1. Main Entry Point (`main.py`)
- Handles HTTP requests (LINE Webhook or Raspberry Pi).
- Initializes dependencies (Adapters, Use Cases).
- Dispatches requests to `LineController` or `ProcessMessageUseCase`.

### 2. Domain & Interfaces (`core/domain/interfaces.py`)
- `ILanguageModel`: Interface for LLM interaction. Now supports `chat_with_tools`.
- `INotionRepository`: Interface for Notion operations. Exposes specific methods like `search_database`, `create_page`.

### 3. Use Cases (`core/use_cases/`)
- `ProcessMessageUseCase`:
  - Orchestrates the conversation.
  - Defines the list of available tools (from `NotionAdapter`).
  - Delegates the execution to `GeminiAdapter` using `chat_with_tools`.
  - No longer handles manual retry loops for JSON parsing, as the SDK handles tool execution cycles.

### 4. Gateways (`core/interfaces/gateways/`)
- `GeminiAdapter`:
  - Implements `ILanguageModel`.
  - Uses `enable_automatic_function_calling=True`.
  - Constructs system instructions with database schemas.
- `NotionAdapter`:
  - Implements `INotionRepository`.
  - Provides concrete implementations for `search_database`, `create_page`, etc.
  - Handles Notion API authentication and error mapping.

## Data Flow (Function Calling)
1. User speaks -> RPi captures audio -> STT -> Text sent to Cloud Function.
2. `ProcessMessageUseCase` initializes Gemini Chat with Notion Tools.
3. Gemini analyzes user text.
   - If information is missing (e.g., ID for update), Gemini calls `search_database`.
   - The SDK automatically executes `NotionAdapter.search_database` and feeds the result back to Gemini.
4. Gemini processes the tool result and decides the next action (e.g., `update_page` or final response).
5. Final text response is returned to RPi for TTS.

## Deployment
- Cloud Functions (Gen 2)
- Environment Variables: `NOTION_API_KEY`, `GEMINI_API_KEY`, `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`.

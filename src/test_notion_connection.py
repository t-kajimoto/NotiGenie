import asyncio
import json
import os
import sys
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load environment variables from .env file
load_dotenv()

async def test_notion_connection():
    """
    Tests the connection to the Notion API by starting the mcp-notion server
    and calling its verify_connection tool using the modern mcp client pattern.
    """
    print("Starting Notion connection test...")

    # Define the command to run the mcp-notion server.
    # Use sys.executable to ensure we use the same python interpreter.
    # It will inherit the environment, including the .env variables loaded by dotenv.
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "notion_api_mcp"],
        env=os.environ,
    )

    try:
        # stdio_client starts the server and provides read/write streams
        async with stdio_client(server_params) as (read, write):
            print("MCP server process started.")
            # ClientSession handles the MCP protocol over the streams
            async with ClientSession(read, write) as session:
                print("MCP client session established.")

                # Initialize the connection
                await session.initialize()
                print("MCP session initialized.")

                # Call the 'verify_connection' tool
                print("\nCalling 'verify_connection' tool...")
                result = await session.call_tool("verify_connection", arguments={})

                print("\n--- Test Result ---")
                # The result from a tool call is an object, not just a dict.
                # We can check for errors and access the content.
                if result.isError:
                    print("\n❌ Tool call failed.")
                    # The content of an error result is typically a list of text blocks.
                    if result.content:
                        for content_block in result.content:
                            if hasattr(content_block, 'text'):
                                print(f"Error details: {content_block.text}")
                else:
                    # Successful tool calls have a 'structuredContent' attribute
                    if result.structuredContent:
                        print(json.dumps(result.structuredContent, indent=2))
                        if result.structuredContent.get("status") == "success":
                            print("\n✅ Notion connection successful!")
                        else:
                            print("\n❌ Notion connection failed.")
                            if result.structuredContent.get("error"):
                                print("Error details:", result.structuredContent.get("error"))
                    else:
                        print("\n❓ Test finished with no structured content. Raw content:")
                        print(result.content)

    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
        # The traceback can be helpful for debugging issues with the test script itself
        import traceback
        traceback.print_exc()

    finally:
        print("\nConnection test finished.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(test_notion_connection())

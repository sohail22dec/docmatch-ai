# test_mcp.py
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.core.tools import get_mcp_tools

async def main():
    print("Connecting to MCP servers...")
    try:
        tools = await get_mcp_tools()
        print(f"Successfully loaded {len(tools)} tools!")
        for tool in tools:
            print(f"- {tool.name}: {tool.description}")
            
    except Exception as e:
        print(f"Error loading tools: {e}")

if __name__ == "__main__":
    asyncio.run(main())

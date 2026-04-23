# backend/app/core/tools.py

import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from app.core.config import settings

# Get the absolute path to our custom medical tools MCP server
current_dir = os.path.dirname(os.path.abspath(__file__))
medical_tools_mcp_path = os.path.join(os.path.dirname(current_dir), "mcp_servers", "medical_tools.py")

async def get_mcp_tools():
    """
    Initializes connections to our MCP servers and returns a combined list
    of LangChain-compatible tools.
    """
    
    # Environment variables for our tools
    env_vars = os.environ.copy()
    if settings.TAVILY_API_KEY:
        env_vars["TAVILY_API_KEY"] = settings.TAVILY_API_KEY
    if settings.GOOGLE_MAPS_API_KEY:
        env_vars["GOOGLE_MAPS_API_KEY"] = settings.GOOGLE_MAPS_API_KEY

    # Define our MCP servers configuration
    client = MultiServerMCPClient({
        # Our Custom Medical Tools Server (Handles both Search and Maps)
        "medical_tools_server": {
            "transport": "stdio",
            # This runs our local python file
            "command": "uv",
            "args": ["run", medical_tools_mcp_path],
            "env": env_vars
        }
    })

    # This async call connects to the servers, requests their tool schemas, 
    # and converts them into LangChain `@tool` objects.
    tools = await client.get_tools()
    
    return tools

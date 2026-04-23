# backend/app/mcp_servers/google_maps.py

import os
import sys
import httpx
from fastmcp import FastMCP
from tavily import TavilyClient

# Ensure we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.core.config import settings

# Initialize FastMCP
mcp = FastMCP("Medical Tools Server")

@mcp.tool()
def search_medical_web(query: str, search_depth: str = "advanced") -> str:
    """
    Searches the web for medical literature, symptoms, or general medical information.
    Uses the Tavily search API.
    
    Args:
        query: The search query (e.g., "symptoms of strep throat" or "latest treatments for type 2 diabetes").
        search_depth: "basic" for quick answers, "advanced" for deep research. Defaults to "advanced".
    
    Returns:
        A string containing the summarized search results.
    """
    if not settings.TAVILY_API_KEY:
        return "Error: TAVILY_API_KEY is not configured in the environment."
        
    try:
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        response = client.search(query=query, search_depth=search_depth)
        
        results = response.get("results", [])
        if not results:
            return "No relevant medical information found."
            
        formatted_results = [f"Search Results for '{query}':"]
        for i, res in enumerate(results):
            formatted_results.append(f"{i+1}. {res.get('title')}\n   {res.get('content')}\n   Source: {res.get('url')}")
            
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Error occurred during web search: {str(e)}"

@mcp.tool()
def find_medical_facilities(location: str, facility_type: str = "hospital") -> str:
    """
    Finds medical facilities (hospitals, clinics, doctors) near a specified location.
    
    Args:
        location: The city, neighborhood, or address to search in (e.g., "Downtown Seattle" or "New York City").
        facility_type: The specific type of facility (e.g., "hospital", "clinic", "cardiologist", "pediatrician").
            Defaults to "hospital".
            
    Returns:
        A formatted string containing a list of matching medical facilities, their addresses, and ratings.
    """
    if not settings.GOOGLE_MAPS_API_KEY:
        return "Error: GOOGLE_MAPS_API_KEY is not configured in the environment."

    query = f"{facility_type} near {location}"
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    
    params = {
        "query": query,
        "key": settings.GOOGLE_MAPS_API_KEY,
    }

    try:
        # Use sync httpx client since FastMCP tools can be sync
        with httpx.Client() as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "OK":
                return f"Google Maps API returned status: {data.get('status')}. No results found."
            
            results = data.get("results", [])
            if not results:
                return f"No {facility_type}s found near {location}."
            
            formatted_results = [f"Found {len(results)} facilities near {location}:"]
            
            for i, place in enumerate(results[:10]): # Limit to top 10
                name = place.get("name", "Unknown Name")
                address = place.get("formatted_address", "Unknown Address")
                rating = place.get("rating", "N/A")
                formatted_results.append(f"{i+1}. {name}\n   Address: {address}\n   Rating: {rating}/5.0")
                
            return "\n\n".join(formatted_results)
            
    except httpx.HTTPError as e:
        return f"HTTP error occurred while calling Google Maps API: {str(e)}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

if __name__ == "__main__":
    # This runs the MCP server via stdio transport by default
    mcp.run()

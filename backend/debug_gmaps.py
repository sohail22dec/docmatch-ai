import httpx, sys
sys.path.insert(0, ".")
from app.core.config import settings

# Test Google Maps with a real lat/lng (use Karachi coordinates for testing)
lat, lng = 24.8607, 67.0011  # Karachi
url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
params = {
    "location": f"{lat},{lng}",
    "radius": 10000,
    "keyword": "Gynecologist",
    "key": settings.GOOGLE_MAPS_API_KEY,
}
with httpx.Client(timeout=10) as client:
    resp = client.get(url, params=params)
data = resp.json()
print("Status:", data.get("status"))
print("Error message:", data.get("error_message", "none"))
print("Results count:", len(data.get("results", [])))
if data.get("results"):
    print("First result:", data["results"][0].get("name"), data["results"][0].get("vicinity"))

import logging
import httpx
from typing import Optional

from app.core.config import settings
from .google_maps_models import Clinic

logger = logging.getLogger(__name__)


class GoogleMapsService:
    """
    Pure infrastructure service for querying Google Maps Places Text Search API.
    Does NOT depend on LangGraph, MCP, or Planner logic.
    """

    PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_MAPS_API_KEY

    async def search_clinics(
        self,
        specialty: str,
        city: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> list[Clinic]:
        """
        Searches for up to 10 medical clinics/specialists matching `specialty`.
        Supports explicit `city` or `latitude`/`longitude` coordinate queries.
        Returns a list of structured `Clinic` objects.
        """
        if not self.api_key:
            logger.warning("GOOGLE_MAPS_API_KEY is not configured in environment.")
            return []

        if latitude is not None and longitude is not None:
            query = f"{specialty} clinic"
            params = {
                "query": query,
                "location": f"{latitude},{longitude}",
                "radius": "10000",
                "key": self.api_key,
            }
        else:
            city_name = city or "nearby"
            query = f"{specialty} in {city_name}"
            params = {
                "query": query,
                "key": self.api_key,
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.PLACES_TEXT_SEARCH_URL,
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

            status = data.get("status")
            if status != "OK":
                logger.warning(f"Google Maps API returned non-OK status: {status}")
                return []

            results = data.get("results", [])
            clinics: list[Clinic] = []

            for place in results[:10]:  # Limit to top 10
                name = place.get("name", "Unknown Name")
                address = place.get("formatted_address", "Unknown Address")
                rating = place.get("rating")
                place_id = place.get("place_id", "")

                clinics.append(
                    Clinic(
                        name=name,
                        address=address,
                        rating=rating if isinstance(rating, (int, float)) else None,
                        place_id=place_id,
                    )
                )

            return clinics

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during Google Maps Places API search: {e}")
            return []
        except Exception as e:
            logger.exception(f"Unexpected error in search_clinics: {e}")
            return []

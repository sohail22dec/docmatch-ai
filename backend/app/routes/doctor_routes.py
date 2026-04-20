from fastapi import APIRouter, Query
from app.services import doctor_service

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("/")
def get_doctors():
    doctors = doctor_service.get_all_doctors()
    return {"doctors": doctors}


@router.get("/nearby")
def get_nearby_doctors(
    lat: float = Query(..., description="User latitude"),
    lng: float = Query(..., description="User longitude"),
):
    doctors = doctor_service.get_nearby_doctors(lat, lng)
    return {"doctors": doctors}

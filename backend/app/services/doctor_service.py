from app.data.doctors import doctors_db
from app.utils.distance import calculate_haversine_distance

def get_all_doctors():
    return doctors_db

def get_nearby_doctors(user_lat: float, user_lng: float, max_distance_km: float = 5.0):
    nearby_doctors = []
    for doctor in doctors_db:
        distance = calculate_haversine_distance(user_lat, user_lng, doctor["lat"], doctor["lng"])
        if distance <= max_distance_km:
            doctor_with_distance = doctor.copy()
            doctor_with_distance["distance_km"] = round(distance, 2)
            nearby_doctors.append(doctor_with_distance)
            
    # Sort by closest first
    nearby_doctors.sort(key=lambda x: x["distance_km"])
    return nearby_doctors

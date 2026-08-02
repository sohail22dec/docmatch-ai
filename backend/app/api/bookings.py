from fastapi import APIRouter, HTTPException
from app.booking import (
    BookingCreateRequest,
    BookingService,
    BookingValidationError,
    SlotConflictError,
)

router = APIRouter(tags=["Bookings"])
_booking_service = BookingService()


@router.post("/bookings", status_code=201)
async def create_booking_endpoint(req: BookingCreateRequest):
    try:
        booking = await _booking_service.create_booking(req)
        return {
            "success": True,
            "booking": booking.model_dump(),
            "message": (
                f"Your appointment has been successfully booked! "
                f"A confirmation email has been sent to {booking.patient_email}."
            ),
        }
    except BookingValidationError as ve:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "VALIDATION_ERROR", "details": ve.errors},
        )
    except SlotConflictError as sce:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "SLOT_UNAVAILABLE",
                "message": sce.message,
                "suggested_slots": sce.suggested_slots,
            },
        )

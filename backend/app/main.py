from fastapi import FastAPI
from app.routes.doctor_routes import router as doctor_router

app = FastAPI(title="DocMatch AI", description="AI-powered doctor recommendation API")

app.include_router(doctor_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the DocMatch AI API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

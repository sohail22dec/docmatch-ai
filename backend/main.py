# backend/main.py

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Initialize FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-Agent Medical Assistant API powered by LangGraph & Groq",
    version="1.0.0",
)

# Allow our future Next.js frontend to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple endpoint to verify the server is running."""
    return {"status": "ok", "app": settings.APP_NAME, "database": "Supabase Connected"}


if __name__ == "__main__":
    # This tells uvicorn to run our 'app' object from this 'main' file
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

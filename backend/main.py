import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.agent.graph import build_graph
from app.api.chat import router as chat_router
from app.api.sessions import router as sessions_router
from app.api.bookings import router as bookings_router
from dotenv import load_dotenv

# Load .env into os.environ for LangSmith tracing
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.graph = await build_graph()
    yield
    pass


# Initialize FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-Agent Medical Assistant API powered by LangGraph & Groq",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API routers
app.include_router(chat_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(bookings_router, prefix="/api")

# Allow Next.js frontend to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://docmatch-ai.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "database": "Supabase Connected"}


if __name__ == "__main__":
    # This tells uvicorn to run our 'app' object from this 'main' file
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

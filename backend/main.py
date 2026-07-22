import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.agent.graph import build_graph
from app.api.routes import router as chat_router
from dotenv import load_dotenv

# Load .env into os.environ for LangSmith tracing
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Building and caching LangGraph on startup...")
    app.state.graph = await build_graph()
    print("LangGraph is ready!")
    yield
    # Teardown (if necessary)
    pass


# Initialize FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-Agent Medical Assistant API powered by LangGraph & Groq",
    version="1.0.0",
    lifespan=lifespan,
)

# Include the chat router
app.include_router(chat_router, prefix="/api", tags=["Chat"])

# Allow Next.js frontend to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

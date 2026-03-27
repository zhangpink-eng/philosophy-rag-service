from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.router import router
from api.router_user import router as user_router
from api.router_session import router as session_router
from api.router_memory import router as memory_router
from api.router_safety import router as safety_router
from api.router_workshop import router as workshop_router
from api.router_assist import router as assist_router
from config import settings

# Create FastAPI app
app = FastAPI(
    title="Philosophia RAG Service",
    description="RAG service for Oscar Brenifier's philosophy practice materials",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include routers
app.include_router(router)
app.include_router(user_router)
app.include_router(session_router)
app.include_router(memory_router)
app.include_router(safety_router)
app.include_router(workshop_router)
app.include_router(assist_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Philosophia RAG Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    try:
        from db.postgres_client import init_db
        init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization skipped: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

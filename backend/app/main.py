import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Base, engine
from app.api.v1.router import api_router

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Recruitment MIS Automation & Productivity Intelligence"
)

# Exception handler to safely handle any validation errors containing raw binary input
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    safe_errors = []
    for err in exc.errors():
        safe_err = dict(err)
        if "input" in safe_err and isinstance(safe_err["input"], (bytes, bytearray)):
            safe_err["input"] = f"<binary upload: {len(safe_err['input'])} bytes>"
        safe_errors.append(safe_err)
    return JSONResponse(status_code=422, content={"detail": safe_errors})

# CORS Middleware (Allows frontend Next.js/Vite dev servers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "version": settings.VERSION}


# Mount built frontend static files if dist folder exists
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

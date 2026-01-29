"""FastAPI web frontend for LinkedIn Post Creation System."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from src.config import settings
from src.web.admin import admin_router

# Setup
app = FastAPI(title="LinkedIn Post Creation System")

# Static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Include admin router (always available)
app.include_router(admin_router)

# Include user router if enabled
if settings.user_frontend_enabled:
    from src.web.user import user_router
    app.include_router(user_router)
else:
    # Root redirect only when user frontend is disabled
    @app.get("/")
    async def root():
        """Redirect root to admin frontend."""
        return RedirectResponse(url="/admin", status_code=302)


def run_web():
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_web()

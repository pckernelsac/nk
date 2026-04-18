# app.py — entry compatibility (Passenger / scripts); real app lives in main.py
from main import app, create_app

__all__ = ["app", "create_app"]

if __name__ == "__main__":
    import os

    import uvicorn

    _dev = os.environ.get("APP_ENV", "development") != "production"
    uvicorn.run(
        "main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=_dev,
    )

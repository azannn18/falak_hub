from fastapi import FastAPI

app = FastAPI()

try:
    try:
        from backend.main import app as real_app
    except ImportError:
        from main import app as real_app
    app.mount("/", real_app)
except Exception as e:
    import traceback
    err = traceback.format_exc()
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"])
    def catch_all(path: str):
        return {"error": "Startup Crash", "traceback": err}

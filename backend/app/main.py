from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import Base, SessionLocal, add_missing_columns, engine
from .routers import chat, documents, org, tasks, team
from .seed import seed

settings = get_settings()



@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    add_missing_columns(engine)
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed(db)
    yield


app = FastAPI(title="Görevlendirme Asistanı", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (org.router, documents.router, tasks.router, team.router, chat.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True, "llm_provider": settings.llm_provider}


# Derlenmiş frontend varsa aynı sunucudan servis edilir (tek imajla kurum içi kurulum).
_dist = Path(settings.frontend_dist).resolve()
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = _dist / path
        if path and f.is_file() and _dist in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(_dist / "index.html")

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.routers import api_keys, auth, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Pulsecity Admin",
    description="IAM service for user management, roles, and API keys",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(api_keys.router)


@app.get("/health")
def health():
    return {"status": "ok"}

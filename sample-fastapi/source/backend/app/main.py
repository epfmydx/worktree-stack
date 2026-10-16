from fastapi import FastAPI

from app.routes import todos

app = FastAPI(title="sample-fastapi")
app.include_router(todos.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

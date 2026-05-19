from fastapi import FastAPI
from api.routes import router

app = FastAPI(
    title="QuantumFlow AI",
    description="Real-time market intelligence monolith",
    version="1.0.0",
)

app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "QuantumFlow Monolith is operational", "phase": 1}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

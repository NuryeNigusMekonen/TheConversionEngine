from fastapi import FastAPI

from agent.api.routes import router

app = FastAPI(
    title="The Conversion Engine",
    description="High-level scaffold for the Tenacious conversion engine.",
    version="0.1.0",
)
app.include_router(router)

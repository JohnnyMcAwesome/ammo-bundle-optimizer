from fastapi import FastAPI
from api.optimizer import router as optimizer_router

app = FastAPI(title="Ammo Bundle Optimizer")

app.include_router(optimizer_router, prefix="/optimize", tags=["optimizer"])

@app.get("/")
async def root():
    return {"message": "Ammo Bundle Optimizer API is running."}


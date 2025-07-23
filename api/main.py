# api/main.py

from fastapi import FastAPI
from api import optimizer
from api.schemas import OptimizeRequest

app = FastAPI()

@app.post("/optimize")
def optimize_ammo_bundle(request: OptimizeRequest):
    return optimizer.optimize_ammo_bundle(request)


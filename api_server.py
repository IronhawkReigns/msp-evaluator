# api_server.py
from fastapi import FastAPI
from vector_writer import run_from_msp_name

app = FastAPI()

@app.post("/run/{msp_name}")
def run_evaluation(msp_name: str):
    run_from_msp_name(msp_name)
    return {"status": "Completed", "msp": msp_name}

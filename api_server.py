# api_server.py
from fastapi import FastAPI
from vector_writer import run_from_msp_name
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

@app.post("/run/{msp_name}")
def run_evaluation(msp_name: str):
    run_from_msp_name(msp_name)
    return {"status": "success", "message": f"{msp_name} data written to ChromaDB"}
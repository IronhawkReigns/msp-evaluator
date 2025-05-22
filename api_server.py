# api_server.py
from fastapi import FastAPI
from vector_writer import run_from_msp_name
import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

app = FastAPI()

@app.post("/run/{msp_name}")
def run_evaluation(msp_name: str):
    try:
        run_from_msp_name(msp_name)
        return {"message": f"{msp_name} written to ChromaDB successfully."}
    except Exception as e:
        return {"error": str(e)}
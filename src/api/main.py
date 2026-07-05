import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Ensure we can import from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import settings
from src.api.routes import router
from src.models.registry import load_model

load_dotenv()

app = FastAPI(
    title="CityVerse API",
    description="FastAPI Backend for Dubai Smart City Digital Twin",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    print("Loading registered machine learning models into memory...")
    app.state.models = {}
    
    domains = ["traffic", "tourism", "energy", "water", "air_quality", "public_transport", "carbon"]
    for domain in domains:
        try:
            app.state.models[domain] = load_model(domain)
            print(f"  [OK] Loaded {domain} model.")
        except Exception as e:
            print(f"  [ERROR] Failed to load {domain} model: {e}")

app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Welcome to CityVerse Dubai Digital Twin Backend API. Visit /docs for Swagger UI."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
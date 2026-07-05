# test_config.py
from src.config import settings

print("Configurations Loaded Successfully!")
print(f"Database URL: {settings.database_url}")
print(f"API Port: {settings.API_PORT}")
print(f"Gemini API Key Loaded: {'Yes' if settings.GEMINI_API_KEY else 'No'}")
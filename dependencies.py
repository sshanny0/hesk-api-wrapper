import os
import secrets
from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from dotenv import load_dotenv
from database import SessionLocal

load_dotenv()
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_api_key(api_key_header: str = Security(api_key_header)):
    # Tanpa API_KEY di server, semua request ditolak; bukan dibiarkan lolos.
    if API_KEY and api_key_header and secrets.compare_digest(api_key_header, API_KEY):
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API Key tidak valid atau tidak ditemukan"
    )

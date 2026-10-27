from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from dependencies import get_db, get_api_key
from routers import tickets

app = FastAPI(
    title="Hesk API Wrapper", 
    description="API Gateway modular untuk Hesk", 
    docs_url="/docs"
)

# Integrasikan semua endpoint dari folder routers
app.include_router(tickets.router)

@app.get("/")
def read_root(db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "Terhubung"
    except Exception as e:
        db_status = f"Gagal terhubung: {str(e)}"
        
    return {
        "api_status": "Online", 
        "database_status": db_status,
        "message": "Hesk API Wrapper is running"
    }
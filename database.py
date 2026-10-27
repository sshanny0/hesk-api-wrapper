import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sshtunnel import SSHTunnelForwarder

load_dotenv()

# Kredensial DB
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")

# Kredensial SSH
SSH_HOST = os.getenv("SSH_HOST")
SSH_USER = os.getenv("SSH_USER")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")
SSH_PORT = int(os.getenv("SSH_PORT"))
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH")

# Dari sisi server SSH, MariaDB Hesk hanya menerima user lokal.
# Kalau DB_HOST sama dengan host SSH, sambungkan ke 127.0.0.1 supaya
# MariaDB melihat koneksi sebagai localhost, bukan hostname publik server.
REMOTE_DB_HOST = "127.0.0.1" if DB_HOST in {SSH_HOST, "localhost"} else DB_HOST

# Konfigurasi parameter SSH (mendukung password atau private key)
ssh_kwargs = {
    "ssh_address_or_host": (SSH_HOST, SSH_PORT),
    "ssh_username": SSH_USER,
    "remote_bind_address": (REMOTE_DB_HOST, DB_PORT)
}

if SSH_KEY_PATH:
    ssh_kwargs["ssh_pkey"] = SSH_KEY_PATH
else:
    ssh_kwargs["ssh_password"] = SSH_PASSWORD

# Buka SSH Tunnel
tunnel = SSHTunnelForwarder(**ssh_kwargs)
tunnel.start()

# URL.create meng-encode karakter khusus di password (misalnya @) supaya tidak
# tertukar dengan pemisah host pada connection string.
SQLALCHEMY_DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host="127.0.0.1",
    port=tunnel.local_bind_port,
    database=DB_NAME,
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
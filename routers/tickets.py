from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, File, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session
import html
import os
import re
import secrets

import models
import schemas
import hesk_storage
from dependencies import get_db, get_api_key

# Menerapkan prefix dan proteksi API Key secara global untuk file ini
router = APIRouter(
    prefix="/api/tickets",
    tags=["Tickets"],
    dependencies=[Depends(get_api_key)] 
)

# Disamakan dengan pengaturan lampiran di hesk_settings.inc.php
ALLOWED_EXTENSIONS = {"gif", "jpg", "png", "zip", "rar", "csv", "doc", "docx", "xls", "xlsx", "txt", "pdf"}
MAX_ATTACHMENT_SIZE = 2 * 1024 * 1024
# Karakter trackid yang dipakai Hesk (tanpa huruf/angka yang mudah tertukar)
TRACKID_CHARS = "AEUYBDGHJLMNPQRSTVWXZ123456789"
HESK_TIMEZONE = ZoneInfo(os.getenv("HESK_TIMEZONE", "Asia/Jakarta"))

def generate_trackid(db: Session):
    while True:
        raw = "".join(secrets.choice(TRACKID_CHARS) for _ in range(10))
        trackid = f"{raw[:3]}-{raw[3:6]}-{raw[6:]}"
        if not db.query(models.Ticket.id).filter(models.Ticket.trackid == trackid).first():
            return trackid

# Hesk menyimpan teks dalam bentuk ter-escape; teks mentah akan dirender sebagai HTML di panel admin.
def hesk_text(value: str):
    return html.escape(value.strip(), quote=True)

def hesk_html(value: str):
    return hesk_text(value).replace("\r\n", "\n").replace("\n", "<br />\n")

def history_entry(action: str):
    now = datetime.now(HESK_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    return f'<li class="smaller">{now} | {action} by Customer</li>'

def find_ticket(trackid: str, db: Session):
    ticket = db.query(models.Ticket).filter(models.Ticket.trackid == trackid).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    return ticket

def get_or_create_customer(name: str, email: str, db: Session):
    customer = db.query(models.Customer).filter(func.lower(models.Customer.email) == email.lower()).first()
    if customer:
        return customer
    customer = models.Customer(name=name, email=email, verified=0)
    db.add(customer)
    db.flush()
    return customer

def requester_id(ticket: models.Ticket, db: Session):
    link = db.query(models.TicketToCustomer).filter(
        models.TicketToCustomer.ticket_id == ticket.id,
        models.TicketToCustomer.customer_type == "REQUESTER",
    ).first()
    return link.customer_id if link else None

@router.post("/", response_model=schemas.TicketResponse)
def create_ticket(ticket: schemas.TicketCreate, request: Request, db: Session = Depends(get_db)):
    if not db.query(models.Category.id).filter(models.Category.id == ticket.category).first():
        raise HTTPException(status_code=400, detail="Kategori tidak ditemukan")

    name = hesk_text(ticket.u_name)
    email = ticket.u_email.strip()
    db_ticket = models.Ticket(
        trackid=generate_trackid(db), u_name=name, u_email=email,
        category=ticket.category, priority=ticket.priority, subject=hesk_text(ticket.subject),
        message=hesk_text(ticket.message), message_html=hesk_html(ticket.message),
        status=0, attachments="", dt=func.now(), ip=request.client.host if request.client else "",
        history=history_entry("submitted"),
    )
    # Tabel Hesk memakai MyISAM (tanpa transaksi), jadi tiap insert langsung tersimpan.
    db.add(db_ticket)
    db.flush()
    customer = get_or_create_customer(name, email, db)
    db.add(models.TicketToCustomer(ticket_id=db_ticket.id, customer_id=customer.id, customer_type="REQUESTER"))
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

@router.get("/{trackid}", response_model=schemas.TicketResponse)
def get_ticket(trackid: str, db: Session = Depends(get_db)):
    return find_ticket(trackid, db)

@router.get("/user/{u_email}", response_model=list[schemas.TicketResponse])
def get_user_tickets(u_email: str, db: Session = Depends(get_db)):
    return db.query(models.Ticket).filter(models.Ticket.u_email == u_email).order_by(models.Ticket.id.desc()).all()

@router.get("/{trackid}/replies", response_model=list[schemas.ReplyResponse])
def get_ticket_replies(trackid: str, db: Session = Depends(get_db)):
    ticket = find_ticket(trackid, db)
    return db.query(models.Reply).filter(models.Reply.replyto == ticket.id).order_by(models.Reply.id.asc()).all()

@router.post("/{trackid}/replies", response_model=schemas.ReplyResponse)
def create_reply(trackid: str, reply: schemas.ReplyCreate, db: Session = Depends(get_db)):
    ticket = find_ticket(trackid, db)
    if ticket.locked == "1":
        raise HTTPException(status_code=403, detail="Tiket dikunci, tidak bisa dibalas")

    new_reply = models.Reply(
        replyto=ticket.id, name=hesk_text(reply.name), message=hesk_text(reply.message),
        message_html=hesk_html(reply.message), dt=func.now(), attachments="", staffid=0,
        customer_id=requester_id(ticket, db),
    )
    # Status 1 = "Waiting reply": balasan pelanggan menunggu tanggapan staf.
    ticket.status = 1
    ticket.replies = (ticket.replies or 0) + 1
    ticket.lastreplier = "0"
    db.add(new_reply)
    db.commit()
    db.refresh(new_reply)
    return new_reply

@router.patch("/{trackid}/close")
def close_ticket(trackid: str, db: Session = Depends(get_db)):
    ticket = find_ticket(trackid, db)
    if ticket.status != 3:
        ticket.status = 3
        ticket.closedat = func.now()
        ticket.closedby = 0
        ticket.history = (ticket.history or "") + history_entry("closed")
        db.commit()
    return {"message": "Tiket berhasil ditutup", "trackid": trackid, "status": 3}

def clean_filename(filename: str):
    name = os.path.basename((filename or "").replace("\\", "/"))
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return name[:200]

@router.post("/{trackid}/attachments")
def upload_attachment(trackid: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    ticket = find_ticket(trackid, db)

    real_name = clean_filename(file.filename)
    ext = real_name.rsplit(".", 1)[-1].lower() if "." in real_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Ekstensi file tidak diizinkan")

    data = file.file.read(MAX_ATTACHMENT_SIZE + 1)
    if len(data) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(status_code=413, detail="Ukuran file melebihi 2 MB")
    if not data:
        raise HTTPException(status_code=400, detail="File kosong")

    saved_name = f"{trackid}_{secrets.token_hex(16)}.{ext}"
    try:
        hesk_storage.save_attachment(saved_name, data)
    except Exception:
        raise HTTPException(status_code=502, detail="Gagal menyimpan file ke server Hesk")

    try:
        attachment = models.Attachment(ticket_id=trackid, saved_name=saved_name, real_name=real_name, size=len(data), type="0")
        db.add(attachment)
        db.flush()
        # Format kolom attachments di Hesk: "att_id#nama_file," untuk tiap lampiran
        ticket.attachments = (ticket.attachments or "") + f"{attachment.att_id}#{real_name},"
        db.commit()
    except Exception:
        db.rollback()
        try:
            hesk_storage.delete_attachment(saved_name)
        except Exception:
            pass
        raise

    return {"message": "Lampiran disimpan", "filename": real_name, "att_id": attachment.att_id}

from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base
from os import getenv

# Hesk mewajibkan custom1..custom100 (NOT NULL tanpa default) saat insert tiket.
HeskCustomFields = type(
    "HeskCustomFields",
    (),
    {f"custom{i}": Column(Text, nullable=False, default="") for i in range(1, 101)},
)

class Ticket(HeskCustomFields, Base):
    __tablename__ = getenv("TABLE_TICKETS")

    id = Column(Integer, primary_key=True, index=True)
    trackid = Column(String(13), unique=True, index=True)
    u_name = Column(String(255)) 
    u_email = Column(String(1000)) 
    subject = Column(String(255)) 
    message = Column(Text) 
    message_html = Column(Text)
    status = Column(Integer, default=0)
    category = Column(Integer, default=1) 
    priority = Column(Integer, default=3) 
    attachments = Column(Text, default="")
    dt = Column(DateTime)
    lastchange = Column(DateTime)
    closedat = Column(DateTime)
    closedby = Column(Integer)
    ip = Column(String(45), default="")
    openedby = Column(Integer, default=0)
    replies = Column(Integer, default=0)
    lastreplier = Column(String(1), default="0")
    locked = Column(String(1), default="0")
    merged = Column(Text, nullable=False, default="")
    history = Column(Text, nullable=False, default="")

class Reply(Base):
    __tablename__ = getenv("TABLE_REPLIES")

    id = Column(Integer, primary_key=True, index=True)
    replyto = Column(Integer, index=True) # Merujuk ke kolom 'id' di tabel hesk_tickets
    name = Column(String(255))
    message = Column(Text)
    message_html = Column(Text)
    dt = Column(DateTime)
    attachments = Column(Text, default="")
    staffid = Column(Integer, default=0)
    customer_id = Column(Integer)

class Attachment(Base):
    __tablename__ = "hesk_attachments"

    att_id = Column(Integer, primary_key=True)
    ticket_id = Column(String(13), index=True) # Berisi trackid, bukan id numerik
    saved_name = Column(String(255))
    real_name = Column(String(255))
    size = Column(Integer, default=0)
    type = Column(String(1), default="0")

class Customer(Base):
    __tablename__ = "hesk_customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), default="")
    email = Column(String(255))
    verified = Column(Integer, default=0)

class TicketToCustomer(Base):
    __tablename__ = "hesk_ticket_to_customer"

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, index=True)
    customer_id = Column(Integer, index=True)
    customer_type = Column(String(9), default="REQUESTER")

class Category(Base):
    __tablename__ = "hesk_categories"

    id = Column(Integer, primary_key=True)

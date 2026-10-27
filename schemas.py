from pydantic import BaseModel, Field

class TicketBase(BaseModel):
    u_name: str
    u_email: str
    subject: str
    message: str
    category: int = 1
    priority: int = 3

# Validasi hanya untuk input; data lama di Hesk tidak selalu memenuhi aturan ini.
class TicketCreate(TicketBase):
    u_name: str = Field(min_length=1, max_length=255)
    u_email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    subject: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    priority: int = Field(default=3, ge=0, le=3)

class TicketResponse(TicketBase):
    trackid: str
    status: int
    attachments: str = ""

    class Config:
        from_attributes = True

class ReplyResponse(BaseModel):
    name: str
    message: str

    class Config:
        from_attributes = True

class ReplyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)

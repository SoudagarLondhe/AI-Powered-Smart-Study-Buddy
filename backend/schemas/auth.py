from typing import Optional
from pydantic import BaseModel, Field, EmailStr

class SignUpIn(BaseModel):
    user_email: EmailStr
    user_password: str = Field(min_length=1)
    user_firstname: Optional[str] = None
    user_lastname: Optional[str] = None
    user_university: Optional[str] = None
    user_currentsem: Optional[str] = None

class LoginIn(BaseModel):
    user_email: EmailStr
    user_password: str = Field(min_length=1)

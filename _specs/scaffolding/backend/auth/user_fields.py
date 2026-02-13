"""This creates a model of input structure to verify that the users' entered fields fit with that of 
the database tables. This is used in webserver.py, for example, to verify that the sign-up form is filled in correctly."""

from pydantic import BaseModel, Field, EmailStr

class UserFields(BaseModel):
    first: str
    last: str
    email: EmailStr
    password: str

class UserLoginFields(BaseModel):
    email: str
    password: str


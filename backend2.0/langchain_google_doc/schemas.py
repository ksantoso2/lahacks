from pydantic import BaseModel

class GoogleDocCreatorInput(BaseModel):
    title: str
    content: str
    access_token: str

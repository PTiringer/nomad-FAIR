from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class ExampleUserInput:
    upload_id: str


class ExampleUserInfo(BaseModel):
    upload_id: str
    user_id: str
    username: str

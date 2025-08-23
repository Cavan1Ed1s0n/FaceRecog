from pydantic import BaseModel
from typing import List


class RegisterFaceResponse(BaseModel):
    id: str
    name: str


class VideoResponse(BaseModel):
    result_path: str

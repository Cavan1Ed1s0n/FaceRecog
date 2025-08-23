from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from search import engine_sync, SessionLocalSync, Base, Face
from schemas import RegisterFaceResponse
from fastapi import HTTPException
from sqlalchemy import text
from PIL import Image
import numpy as np
import cv2

import io
import os, shutil
import tempfile

from ds_pipeline import DeepStreamInference
from utils import draw_bbox

face_ds = DeepStreamInference()
app = FastAPI()

# CORS for frontend access
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.on_event("startup")
def startup():
    with engine_sync.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(conn)
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_embedding
                ON faces USING ivfflat (embedding vector_l2_ops) WITH (lists = 100)
            """
            )
        )


@app.post("/register", response_model=RegisterFaceResponse)
async def register_face(name: str = Form(...), file: UploadFile = File(...)):

    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
        image.save(tmp_file.name)
        tmp_path = tmp_file.name
    image_cv, results = face_ds.run_image(tmp_path)
    # Optionally, remove the temp image after processing
    os.remove(tmp_path)
    if len(results) == 0:
        raise HTTPException(
            status_code=404,
            detail="No face detected in the input image",
        )
    if results[0]["existed"]:
        UserName = results[0]["UserName"]
        match_distance = results[0]["match_distance"]

        raise HTTPException(
            status_code=409,
            detail=f"Face already exists as '{UserName}' with similarity {1 - match_distance:.2f}",
        )
    embedding = results[0]["embedding"]
    new_face = Face(name=name, embedding=embedding.tolist())

    with SessionLocalSync() as db:
        db.add(new_face)
        db.commit()
        db.refresh(new_face)
        return RegisterFaceResponse(id=str(new_face.id), name=new_face.name)


@app.post("/search")
async def search_face(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
        image.save(tmp_file.name)
        tmp_path = tmp_file.name
    # Feed image to DeepStream pipeline
    image_cv, results = face_ds.run_image(tmp_path)
    os.remove(tmp_path)

    if len(results) == 0:  # No faces detected
        raise HTTPException(
            status_code=404,
            detail="No face detected in the input image",
        )

    for result in results:
        draw_bbox(image_cv, result["bbox"], label=result["label"])

    _, jpeg = cv2.imencode(".jpg", image_cv)
    return StreamingResponse(io.BytesIO(jpeg.tobytes()), media_type="image/jpeg")


@app.post("/infer-video")
async def infer_video(file: UploadFile):
    input_path = f"/tmp/{file.filename}"
    os.makedirs(f"assets/videos", exist_ok=True)
    output_path = f"assets/videos/output.mp4"
    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    face_ds.run_video(f"file://{input_path}", output_path)
    os.remove(input_path)

    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename="inference_result.mp4",  # suggested download name
    )

import json
from typing import List, Tuple, Optional

import uuid
import asyncio
import numpy as np
from sqlalchemy import Column, String, text, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from pgvector.sqlalchemy import Vector


Base = declarative_base()


class Face(Base):
    __tablename__ = "faces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    embedding = Column(Vector(512))


DATABASE_URL_SYNC = "postgresql+psycopg2://postgres:123456789@db:5432/face_db"
engine_sync = create_engine(DATABASE_URL_SYNC)
SessionLocalSync = sessionmaker(bind=engine_sync)


class PGVectorFaceSearch:
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def compare_face(self, encoding: np.ndarray) -> Optional[Tuple[float, str, str]]:
        with SessionLocalSync() as session:
            sql = text(
                """
                SELECT id, name, embedding <=> (:query_vector)::vector AS distance
                FROM faces
                ORDER BY distance
            """
            )
            vector_str = json.dumps(encoding.tolist())
            match = session.execute(sql, {"query_vector": vector_str}).fetchone()
            if match:
                return match.distance, str(match.id), match.name
        return None, None, None

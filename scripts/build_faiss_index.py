# scripts/build_faiss_index.py
import ast
import json
import os

import numpy as np
import pandas as pd
from app2.retrieval.faiss_index import FaissIndex  # ← استفاده از کلاس جدید
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")


engine = create_engine(DATABASE_URL)

print("Reading embeddings from database...")

df = pd.read_sql(text("""
    SELECT id, embedding_vector
    FROM asanclipproducts
    WHERE tag_status = 'done'
      AND embedding_vector IS NOT NULL
"""), engine)

print(f"Loaded {len(df)} records with embedding.")

vectors = []
ids = []

for i, v in enumerate(df["embedding_vector"]):
    if v is None:
        continue

    # تبدیل string به لیست
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            try:
                v = ast.literal_eval(v)
            except Exception:
                continue

    vec = np.array(v, dtype="float32")

    if vec.ndim != 1 or len(vec) == 0:
        continue

    vectors.append(vec)
    ids.append(int(df["id"].iloc[i]))

if not vectors:
    raise RuntimeError("No valid embeddings found!")

embeddings = np.vstack(vectors)

print(f"Building FAISS index with {len(ids)} vectors...")

# استفاده از کلاس جدید
faiss_index = FaissIndex(dimension=embeddings.shape[1])
faiss_index.build_index(embeddings, ids)

print("✅ FAISS index built successfully!")
print(f"   Dimension : {embeddings.shape[1]}")
print(f"   Vectors   : {len(ids)}")

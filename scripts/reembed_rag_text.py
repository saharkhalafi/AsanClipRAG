from sqlalchemy import create_engine, text
from app2.embedding.embedding_service import EmbeddingService
import time
import os
import numpy as np


# =========================
# CONFIG
# =========================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment variables")


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


embedder = EmbeddingService()


# =========================
# FETCH DATA
# =========================

def fetch_rows():

    with engine.begin() as conn:

        result = conn.execute(text("""
            SELECT id, rag_text
            FROM asanclipproducts
            WHERE rag_text IS NOT NULL
        """))

        return result.fetchall()



# =========================
# VECTOR FORMAT
# =========================

def vector_to_pgvector(vector):

    if isinstance(vector, np.ndarray):
        vector = vector.tolist()

    return "[" + ",".join(
        str(float(x)) for x in vector
    ) + "]"



# =========================
# UPDATE VECTOR
# =========================

def update_embedding(row_id, vector):

    vector_str = vector_to_pgvector(vector)

    with engine.begin() as conn:

        conn.execute(text("""
            UPDATE asanclipproducts
            SET embedding_vector = CAST(:vec AS vector)
            WHERE id = :id
        """),
        {
            "vec": vector_str,
            "id": row_id
        })



# =========================
# MAIN
# =========================

def main():

    rows = fetch_rows()

    print(f"Total rows to embed: {len(rows)}")


    success = 0
    failed = 0


    for i, row in enumerate(rows):

        try:

            text_input = row.rag_text.strip()


            if not text_input:

                print(
                    f"[SKIP] empty rag_text id={row.id}"
                )

                continue



            # =====================
            # CREATE EMBEDDING
            # =====================

            vector = embedder.embed(text_input)


            if vector is None or len(vector) == 0:

                raise ValueError(
                    "Empty embedding returned"
                )



            if len(vector) != 3072:

                raise ValueError(
                    f"Wrong dimension {len(vector)} expected 3072"
                )



            # =====================
            # SAVE
            # =====================

            update_embedding(
                row.id,
                vector
            )


            success += 1


            print(
                f"[{i+1}/{len(rows)}] OK id={row.id}"
            )


            time.sleep(0.1)



        except Exception as e:

            failed += 1

            print(
                f"[ERROR] id={row.id}: {e}"
            )



    print("\n========== DONE ==========")
    print(f"Success: {success}")
    print(f"Failed: {failed}")



if __name__ == "__main__":
    main()
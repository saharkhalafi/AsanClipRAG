"""Import asanclipproducts rows from Sale1404.sql into the Alembic schema."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

COPY_MARKER = "COPY public.asanclipproducts "
CAPTION_COPY_MARKER = "COPY public.product_captions "
COPY_COLUMNS = (
    "id",
    "name",
    "short_description",
    "description",
    "product_type",
    "occasion",
    "platform",
    "rag_text",
    "tag_status",
    "tag_version",
    "tag_source",
    "search_vector",
    "url",
    "embedding_vector",
)
TARGET_COLUMNS = (
    "id",
    "name",
    "short_description",
    "description",
    "rag_text",
    "product_type",
    "occasion",
    "platform",
    "embedding_vector",
    "tag_status",
    "url",
)


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def wait_for_database(url: str, retries: int = 30, delay: float = 2.0) -> None:
    engine = create_engine(url)
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            print(f"Waiting for PostgreSQL... ({attempt}/{retries}): {exc}")
            time.sleep(delay)
    raise RuntimeError("PostgreSQL did not become ready in time")


def parse_copy_line(line: str) -> list[str | None]:
    fields: list[str | None] = []
    current: list[str] = []
    i = 0
    while i < len(line):
        char = line[i]
        if char == "\\" and i + 1 < len(line):
            nxt = line[i + 1]
            if nxt == "N":
                current = []
                fields.append(None)
                i += 2
                if i < len(line) and line[i] == "\t":
                    i += 1
                continue
            if nxt == "t":
                current.append("\t")
            elif nxt == "n":
                current.append("\n")
            elif nxt == "r":
                current.append("\r")
            elif nxt == "\\":
                current.append("\\")
            else:
                current.append(nxt)
            i += 2
            continue
        if char == "\t":
            fields.append("".join(current))
            current = []
            i += 1
            continue
        current.append(char)
        i += 1
    fields.append("".join(current) if current else None)
    return fields


def iter_copy_rows(sql_path: Path, copy_marker: str, expected_columns: tuple[str, ...]):
    in_copy = False
    with sql_path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            if not in_copy:
                if raw_line.startswith(copy_marker):
                    in_copy = True
                continue
            line = raw_line.rstrip("\n\r")
            if line == "\\.":
                break
            if not line:
                continue
            values = parse_copy_line(line)
            if len(values) != len(expected_columns):
                raise ValueError(
                    f"Unexpected column count {len(values)} for {copy_marker.strip()}"
                )
            yield dict(zip(expected_columns, values))


CAPTION_COPY_COLUMNS = (
    "id",
    "product_id",
    "caption_text",
    "caption_type",
    "occasion_category",
    "priority",
    "is_active",
    "created_at",
    "updated_at",
)


def iter_product_rows(sql_path: Path):
    for row in iter_copy_rows(sql_path, COPY_MARKER, COPY_COLUMNS):
        yield {
            "id": int(row["id"]),
            "name": row["name"],
            "short_description": row["short_description"],
            "description": row["description"],
            "rag_text": row["rag_text"],
            "product_type": row["product_type"],
            "occasion": row["occasion"],
            "platform": row["platform"],
            "embedding_vector": row["embedding_vector"],
            "tag_status": row["tag_status"] or "done",
            "url": row["url"],
        }


def iter_caption_rows(sql_path: Path):
    for row in iter_copy_rows(sql_path, CAPTION_COPY_MARKER, CAPTION_COPY_COLUMNS):
        yield {
            "id": int(row["id"]),
            "product_id": int(row["product_id"]),
            "caption_text": row["caption_text"],
            "caption_type": row["caption_type"] or "occasion",
            "occasion_category": row["occasion_category"],
            "priority": int(row["priority"] or 1),
            "is_active": (row["is_active"] or "t").lower() in ("t", "true", "1"),
        }


def import_products(sql_path: Path, database_url: str, truncate: bool) -> int:
    engine = create_engine(database_url)

    insert_sql = text(
        """
        INSERT INTO asanclipproducts (
            id, name, short_description, description, rag_text,
            product_type, occasion, platform, embedding_vector,
            tag_status, url
        ) VALUES (
            :id, :name, :short_description, :description, :rag_text,
            :product_type, :occasion, :platform,
            :embedding_vector,
            :tag_status, :url
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            short_description = EXCLUDED.short_description,
            description = EXCLUDED.description,
            rag_text = EXCLUDED.rag_text,
            product_type = EXCLUDED.product_type,
            occasion = EXCLUDED.occasion,
            platform = EXCLUDED.platform,
            embedding_vector = EXCLUDED.embedding_vector,
            tag_status = EXCLUDED.tag_status,
            url = EXCLUDED.url
        """
    )

    imported = 0
    batch: list[dict] = []
    batch_size = 200

    with engine.begin() as conn:
        if truncate:
            conn.execute(text("TRUNCATE TABLE asanclipproducts RESTART IDENTITY CASCADE"))
            print("Truncated asanclipproducts")

        for row in iter_product_rows(sql_path):
            batch.append(row)
            if len(batch) >= batch_size:
                conn.execute(insert_sql, batch)
                imported += len(batch)
                print(f"Imported {imported} products...")
                batch.clear()

        if batch:
            conn.execute(insert_sql, batch)
            imported += len(batch)

    return imported


def import_captions(sql_path: Path, database_url: str, truncate: bool) -> int:
    engine = create_engine(database_url)
    insert_sql = text(
        """
        INSERT INTO product_captions (
            id, product_id, caption_text, caption_type,
            occasion_category, priority, is_active
        ) VALUES (
            :id, :product_id, :caption_text, :caption_type,
            :occasion_category, :priority, :is_active
        )
        ON CONFLICT (id) DO UPDATE SET
            product_id = EXCLUDED.product_id,
            caption_text = EXCLUDED.caption_text,
            caption_type = EXCLUDED.caption_type,
            occasion_category = EXCLUDED.occasion_category,
            priority = EXCLUDED.priority,
            is_active = EXCLUDED.is_active
        """
    )

    imported = 0
    batch: list[dict] = []
    batch_size = 500

    with engine.begin() as conn:
        if truncate:
            conn.execute(text("TRUNCATE TABLE product_captions RESTART IDENTITY CASCADE"))
            print("Truncated product_captions")

        for row in iter_caption_rows(sql_path):
            batch.append(row)
            if len(batch) >= batch_size:
                conn.execute(insert_sql, batch)
                imported += len(batch)
                print(f"Imported {imported} captions...")
                batch.clear()

        if batch:
            conn.execute(insert_sql, batch)
            imported += len(batch)

    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Sale1404.sql data")
    parser.add_argument(
        "--sql-file",
        default=os.getenv("SALE1404_SQL_PATH", "Sale1404.sql"),
        help="Path to Sale1404.sql dump",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing rows before import",
    )
    parser.add_argument(
        "--products-only",
        action="store_true",
        help="Import only asanclipproducts",
    )
    parser.add_argument(
        "--captions-only",
        action="store_true",
        help="Import only product_captions",
    )
    args = parser.parse_args()

    if args.products_only and args.captions_only:
        print("Choose either --products-only or --captions-only, not both.", file=sys.stderr)
        return 1

    sql_path = Path(args.sql_file)
    if not sql_path.exists():
        print(f"SQL file not found: {sql_path}", file=sys.stderr)
        return 1

    database_url = get_database_url()
    wait_for_database(database_url)

    import_products_data = not args.captions_only
    import_captions_data = not args.products_only

    if import_products_data:
        print(f"Importing products from {sql_path}...")
        product_count = import_products(sql_path, database_url, truncate=args.truncate)
        print(f"Finished importing {product_count} products.")

    if import_captions_data:
        print(f"Importing captions from {sql_path}...")
        caption_count = import_captions(sql_path, database_url, truncate=args.truncate)
        print(f"Finished importing {caption_count} captions.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

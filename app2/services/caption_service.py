# app2/services/caption_service.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app2.db.models import ProductCaption


class CaptionService:
    def __init__(self, db: Session):
        self.db = db

    def get_captions(self, product_id: int, limit: int = 5) -> List[Dict]:
        """Return suggested captions for a single product."""
        return self.get_unique_captions_for_products([product_id], limit=limit)

    def get_unique_captions_for_products(
        self,
        product_ids: List[int],
        limit: int = 5,
    ) -> List[Dict]:
        """Return up to `limit` unique captions across the given products."""
        normalized_ids: List[int] = []
        for product_id in product_ids:
            try:
                normalized_ids.append(int(product_id))
            except (TypeError, ValueError):
                continue

        if not normalized_ids:
            return []

        rows = (
            self.db.query(ProductCaption)
            .filter(
                ProductCaption.product_id.in_(normalized_ids),
                ProductCaption.is_active == True,
            )
            .order_by(
                ProductCaption.priority.asc(),
                ProductCaption.created_at.desc(),
            )
            .all()
        )

        seen_texts: set[str] = set()
        captions: List[Dict] = []
        for row in rows:
            caption_text = (row.caption_text or "").strip()
            if not caption_text or caption_text in seen_texts:
                continue

            seen_texts.add(caption_text)
            captions.append(
                {
                    "id": row.id,
                    "product_id": row.product_id,
                    "text": caption_text,
                    "type": row.caption_type,
                    "category": row.occasion_category,
                    "priority": row.priority,
                }
            )
            if len(captions) >= limit:
                break

        return captions

    def add_caption(
        self,
        product_id: int,
        text: str,
        caption_type: str = "occasion",
        category: Optional[str] = None,
        priority: int = 1
    ):
        """اضافه کردن یک کپشن به محصول"""
        caption = ProductCaption(
            product_id=product_id,
            caption_text=text.strip(),
            caption_type=caption_type,
            occasion_category=category,
            priority=priority
        )
        self.db.add(caption)
        self.db.commit()
        return caption

    def bulk_add_captions(self, captions_list: List[Dict]):
        """اضافه کپشن"""
        for item in captions_list:
            self.add_caption(
                product_id=item["product_id"],
                text=item["text"],
                caption_type=item.get("type", "occasion"),
                category=item.get("category"),
                priority=item.get("priority", 1)
            )
# app2/services/caption_service.py

from app2.config.constants import USER_CAPTION_LIMIT
from app2.db.models import ProductCaption
from sqlalchemy.orm import Session


class CaptionService:
    def __init__(self, db: Session):
        self.db = db

    def get_captions(self, product_id: int, limit: int = USER_CAPTION_LIMIT) -> list[dict]:
        """Return suggested captions for a single product."""
        return self.get_unique_captions_for_products([product_id], limit=limit)

    def get_unique_captions_for_products(
        self,
        product_ids: list[int],
        limit: int = USER_CAPTION_LIMIT,
    ) -> list[dict]:
        """
        Return up to `limit` unique captions, preferring one per top-ranked product.
        """
        normalized_ids: list[int] = []
        seen_product_ids: set[int] = set()
        for product_id in product_ids:
            try:
                pid = int(product_id)
            except (TypeError, ValueError):
                continue
            if pid in seen_product_ids:
                continue
            seen_product_ids.add(pid)
            normalized_ids.append(pid)

        if not normalized_ids:
            return []

        rows = (
            self.db.query(ProductCaption)
            .filter(
                ProductCaption.product_id.in_(normalized_ids),
                ProductCaption.is_active,
            )
            .order_by(
                ProductCaption.priority.asc(),
                ProductCaption.created_at.desc(),
            )
            .all()
        )

        by_product: dict[int, list[ProductCaption]] = {}
        for row in rows:
            by_product.setdefault(row.product_id, []).append(row)

        seen_texts: set[str] = set()
        captions: list[dict] = []

        # Pass 1: best caption per top product (preserves ranking order)
        for product_id in normalized_ids:
            for row in by_product.get(product_id, []):
                caption_text = (row.caption_text or "").strip()
                if not caption_text or caption_text in seen_texts:
                    continue
                seen_texts.add(caption_text)
                captions.append(self._to_dict(row))
                break
            if len(captions) >= limit:
                return captions[:limit]

        # Pass 2: fill remaining slots from same products
        for row in rows:
            if len(captions) >= limit:
                break
            caption_text = (row.caption_text or "").strip()
            if not caption_text or caption_text in seen_texts:
                continue
            seen_texts.add(caption_text)
            captions.append(self._to_dict(row))

        return captions[:limit]

    @staticmethod
    def _to_dict(row: ProductCaption) -> dict:
        return {
            "id": row.id,
            "product_id": row.product_id,
            "text": (row.caption_text or "").strip(),
            "type": row.caption_type,
            "category": row.occasion_category,
            "priority": row.priority,
        }

    def add_caption(
        self,
        product_id: int,
        text: str,
        caption_type: str = "occasion",
        category: str | None = None,
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

    def bulk_add_captions(self, captions_list: list[dict]):
        """اضافه کپشن"""
        for item in captions_list:
            self.add_caption(
                product_id=item["product_id"],
                text=item["text"],
                caption_type=item.get("type", "occasion"),
                category=item.get("category"),
                priority=item.get("priority", 1)
            )

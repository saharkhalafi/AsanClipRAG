import random
from typing import List, Dict
from sqlalchemy.orm import Session
from app2.db.models import ProductCaption

class CaptionService:
    def __init__(self, db: Session):
        self.db = db

    def get_captions(self, product_id: int, limit: int = 5) -> List[Dict]:
        """دقیقاً limit کپشن با اولویت بالا + shuffle"""
        

        results = (
            self.db.query(ProductCaption)
            .filter(
                ProductCaption.product_id == product_id,
                ProductCaption.is_active == True
            )
            .order_by(ProductCaption.priority.asc())   
            .limit(limit * 2)                        
            .all()
        )

        captions = [
            {
                "id": row.id,
                "text": row.caption_text,
                "type": row.caption_type,
                "category": row.occasion_category,
                "priority": row.priority
            }
            for row in results
        ]

        # اگر کمتر از limit بود، همین‌ها را برگردان
        if len(captions) <= limit:
            return captions

        # Shuffle + برش به limit (رندوم اما با اولویت)
        random.shuffle(captions)
        return captions[:limit]
from app2.db.models import AsanClipProduct
from app2.db.session import get_db
from sqlalchemy.orm import Session


def seed_data() -> None:
    db: Session = next(get_db())

    sample_products = [
        {
            "id": 8502,
            "name": "کلیپ تبریک تولد",
            "short_description": "کلیپ تبریک تولد",
            "description": "کلیپ تبریک تولد",
            "rag_text": "نوع: ویدیو | مناسبت: تولد | کلیپ تبریک تولد",
            "product_type": "ویدیو",
            "occasion": "تولد",
            "tag_status": "done"
        },
        {
            "id": 17481,
            "name": "قالب کلیپ تبریک روز مادر",
            "short_description": "قالب کلیپ تبریک روز مادر",
            "description": "قالب کلیپ تبریک روز مادر",
            "rag_text": "نوع: ویدیو | مناسبت: روز مادر | قالب کلیپ تبریک روز مادر",
            "product_type": "ویدیو",
            "occasion": "روز مادر",
            "tag_status": "done"
        },
        {
            "id": 17459,
            "name": "قالب تبریک روز مادر",
            "short_description": "قالب تبریک روز مادر",
            "description": "قالب تبریک روز مادر",
            "rag_text": "نوع: قالب تبریک | مناسبت: روز مادر | قالب تبریک روز مادر",
            "product_type": "قالب تبریک",
            "occasion": "روز مادر",
            "tag_status": "done"
        }
    ]

    for p in sample_products:
        existing = db.query(AsanClipProduct).filter(AsanClipProduct.id == p["id"]).first()
        if not existing:
            product = AsanClipProduct(**p)
            db.add(product)

    db.commit()
    print(f"Seeded {len(sample_products)} sample products for Docker testing.")

    db.close()


if __name__ == "__main__":
    seed_data()

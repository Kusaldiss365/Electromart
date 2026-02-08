from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.core.db import Base, engine, SessionLocal
from app.models.product import Product
from app.models.promotion import Promotion
from app.models.order import Order
from app.models.faq import FAQ
from app.services.faq_rag import embed


def reset_db(db: Session):
    # Drops & recreates all tables (assessment-friendly)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_products(db: Session):
    products = [
        # --------------------
        # PHONES (Apple)
        # --------------------
        Product(
            sku="APL-IP15-128-BLK",
            name="Apple iPhone 15 (128GB) - Black",
            category="Phone",
            description="6.1-inch Super Retina XDR, A16 Bionic, dual camera system, USB-C, 128GB storage.",
            price=289999,
            in_stock=True
        ),
        Product(
            sku="APL-IP15P-256-BLU",
            name="Apple iPhone 15 Pro (256GB) - Blue Titanium",
            category="Phone",
            description="6.1-inch Super Retina XDR ProMotion, A17 Pro, triple camera, USB-C, 256GB storage.",
            price=429999,
            in_stock=True
        ),
        Product(
            sku="APL-IP14-128-WHT",
            name="Apple iPhone 14 (128GB) - Starlight",
            category="Phone",
            description="6.1-inch Super Retina XDR, A15 Bionic, dual camera, 128GB storage.",
            price=249999,
            in_stock=True
        ),

        # --------------------
        # PHONES (Samsung)
        # --------------------
        Product(
            sku="SAM-S24U-256-BLK",
            name="Samsung Galaxy S24 Ultra (256GB) - Titanium Black",
            category="Phone",
            description="6.8-inch Dynamic AMOLED 2X, Snapdragon 8 Gen 3, 200MP camera, S Pen, 256GB storage.",
            price=479999,
            in_stock=True
        ),
        Product(
            sku="SAM-S24-256-VIO",
            name="Samsung Galaxy S24 (256GB) - Violet",
            category="Phone",
            description="6.2-inch Dynamic AMOLED 2X, flagship performance, triple camera, 256GB storage.",
            price=329999,
            in_stock=True
        ),
        Product(
            sku="SAM-A55-256-BLU",
            name="Samsung Galaxy A55 5G (256GB) - Awesome Blue",
            category="Phone",
            description="6.6-inch Super AMOLED, 50MP camera, long battery life, 256GB storage.",
            price=169999,
            in_stock=True
        ),

        # --------------------
        # LAPTOPS (ASUS)
        # --------------------
        Product(
            sku="ASU-TUF-A15-R7-RTX4050",
            name="ASUS TUF Gaming A15 (Ryzen 7, RTX 4050, 16GB, 512GB)",
            category="Laptop",
            description="15.6-inch FHD 144Hz, Ryzen 7, RTX 4050, 16GB RAM, 512GB SSD. Durable gaming laptop.",
            price=299999,
            in_stock=True
        ),
        Product(
            sku="ASU-ROG-G16-I7-RTX4060",
            name="ASUS ROG Strix G16 (i7, RTX 4060, 16GB, 1TB)",
            category="Laptop",
            description="16-inch gaming laptop, Intel i7, RTX 4060, 16GB RAM, 1TB SSD. High performance for gaming/creator work.",
            price=449999,
            in_stock=True
        ),
        Product(
            sku="ASU-VIVO-15-I5-16-512",
            name="ASUS VivoBook 15 (i5, 16GB, 512GB SSD)",
            category="Laptop",
            description="15.6-inch FHD, Intel i5, 16GB RAM, 512GB SSD. Great for office/university work.",
            price=219999,
            in_stock=True
        ),

        # --------------------
        # LAPTOPS (Apple MacBook)
        # --------------------
        Product(
            sku="APL-MBA-M3-8-256-SLV",
            name="Apple MacBook Air 13 (M3, 8GB, 256GB) - Silver",
            category="Laptop",
            description="Apple M3 chip, 13-inch Retina, 8GB unified memory, 256GB SSD. Ultra portable.",
            price=389999,
            in_stock=True
        ),
        Product(
            sku="APL-MBP-M3P-18-512-SPG",
            name="Apple MacBook Pro 14 (M3 Pro, 18GB, 512GB) - Space Gray",
            category="Laptop",
            description="M3 Pro chip, 14-inch Liquid Retina XDR, 18GB unified memory, 512GB SSD. Pro-grade performance.",
            price=699999,
            in_stock=True
        ),

        # --------------------
        # OTHER ITEMS (kept)
        # --------------------
        Product(
            sku="SAM-TV-55QLED-2024",
            name="Samsung 55\" QLED 4K Smart TV (2024)",
            category="TV",
            description="55-inch QLED 4K UHD, HDR, Smart Hub, voice assistant support.",
            price=279999,
            in_stock=True
        ),
        Product(
            sku="LG-FRIDGE-260L-INV",
            name="LG 260L Inverter Refrigerator (Double Door)",
            category="Fridge",
            description="260L double door, inverter compressor, energy efficient cooling.",
            price=199999,
            in_stock=True
        ),
        Product(
            sku="APL-AIRPODS-PRO2",
            name="Apple AirPods Pro (2nd Gen)",
            category="Audio",
            description="Active Noise Cancellation, Transparency mode, MagSafe charging case.",
            price=99999,
            in_stock=True
        ),
    ]
    db.add_all(products)
    db.flush()  # so IDs exist for orders


def seed_promotions(db: Session):
    now = datetime.now(timezone.utc)

    promos = [
        Promotion(
            title="TV Festival Deals",
            details="Up to 12% off selected Samsung/LG TVs. Limited stocks.",
            discount_percent=12,
            valid_until=now + timedelta(days=10),
        ),
        Promotion(
            title="iPhone + AirPods Bundle",
            details="Buy iPhone 15/15 Pro and get up to 8% off AirPods Pro (2nd Gen).",
            discount_percent=8,
            valid_until=now + timedelta(days=15),
        ),
        Promotion(
            title="Gaming Laptop Week",
            details="Up to 10% off ASUS TUF / ROG gaming laptops (selected SKUs).",
            discount_percent=10,
            valid_until=now + timedelta(days=7),
        ),
        Promotion(
            title="Student Laptop Offer",
            details="Up to 6% off on ASUS VivoBook and MacBook Air for students (with valid student ID).",
            discount_percent=6,
            valid_until=now + timedelta(days=20),
        ),
    ]
    db.add_all(promos)


def seed_orders(db: Session):
    # Map orders → ONE product each
    iphone_15 = db.query(Product).filter_by(sku="APL-IP15-128-BLK").first()
    galaxy_s24u = db.query(Product).filter_by(sku="SAM-S24U-256-BLK").first()
    tuf_a15 = db.query(Product).filter_by(sku="ASU-TUF-A15-R7-RTX4050").first()
    macbook_air = db.query(Product).filter_by(sku="APL-MBA-M3-8-256-SLV").first()
    fridge = db.query(Product).filter_by(sku="LG-FRIDGE-260L-INV").first()
    airpods = db.query(Product).filter_by(sku="APL-AIRPODS-PRO2").first()

    orders = [
        Order(
            id=101,
            customer_name="Kusal",
            status="shipped",
            tracking_number="TRK-LK-000101",
            total_amount=iphone_15.price,
            product_id=iphone_15.id,
        ),
        Order(
            id=102,
            customer_name="Nimal",
            status="processing",
            tracking_number="",
            total_amount=galaxy_s24u.price,
            product_id=galaxy_s24u.id,
        ),
        Order(
            id=103,
            customer_name="Amaya",
            status="delivered",
            tracking_number="TRK-LK-000103",
            total_amount=fridge.price,
            product_id=fridge.id,
        ),
        Order(
            id=104,
            customer_name="Sahan",
            status="delivered",
            tracking_number="TRK-LK-000104",
            total_amount=airpods.price,
            product_id=airpods.id,
        ),
        Order(
            id=105,
            customer_name="Shehan",
            status="shipped",
            tracking_number="TRK-LK-000105",
            total_amount=tuf_a15.price,
            product_id=tuf_a15.id,
        ),
        Order(
            id=106,
            customer_name="Ishara",
            status="processing",
            tracking_number="",
            total_amount=macbook_air.price,
            product_id=macbook_air.id,
        ),
    ]
    db.add_all(orders)


def seed_faqs(db: Session):
    faqs = [
        (
            "What is your return policy?",
            "You can return most items within 7 days of delivery if unused and in original packaging."
        ),
        (
            "How do refunds work?",
            "Refunds are processed after inspection and usually take 5–10 business days."
        ),
        (
            "How long does delivery take?",
            "Delivery takes 1–3 business days in major cities and 3–7 elsewhere."
        ),
        (
            "Do you offer warranty for phones and laptops?",
            "Yes. Most phones and laptops come with a standard manufacturer warranty. Warranty duration depends on the product."
        ),
    ]

    faq_rows = [
        FAQ(
            question=q,
            answer=a,
            embedding=embed(q + " " + a),
        )
        for q, a in faqs
    ]
    db.add_all(faq_rows)


def main():
    db = SessionLocal()
    try:
        reset_db(db)
        seed_products(db)
        seed_promotions(db)
        seed_orders(db)
        seed_faqs(db)
        db.commit()

        print("✅ Seed complete.")
        print("Try:")
        print("- gaming laptop under 300000")
        print("- compare iphone 15 and galaxy s24")
        print("- any promotions for laptops")
        print("- what is order 105")
        print("- return order 104")
    finally:
        db.close()


if __name__ == "__main__":
    main()

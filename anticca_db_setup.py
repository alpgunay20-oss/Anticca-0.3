"""
╔══════════════════════════════════════════════════════════════════╗
║          ANTICCA — MongoDB Profesyonel Kurulum Scripti           ║
║                                                                  ║
║  Bu script MongoDB Atlas'a bağlanarak:                           ║
║  1. Tüm koleksiyonları oluşturur                                  ║
║  2. Tüm index'leri kurar (performans + veri bütünlüğü)           ║
║  3. JSON Schema validasyonlarını uygular                         ║
║  4. Başlangıç verilerini (seed) yükler                           ║
║  5. Admin kullanıcısını oluşturur                                 ║
║                                                                  ║
║  Kullanım:                                                        ║
║    pip install pymongo bcrypt                                    ║
║    python anticca_db_setup.py                                    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import uuid
import bcrypt
import getpass
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.errors import ConnectionFailure, OperationFailure

# ══════════════════════════════════════════════════════════════════
# AYARLAR — Buraya MongoDB Atlas bağlantı bilgilerinizi girin
# ══════════════════════════════════════════════════════════════════

MONGO_URL = input("""
╔══════════════════════════════════════════════════════════════════╗
║  MongoDB Atlas bağlantı URL'nizi girin.                          ║
║  Örnek: mongodb+srv://kullanici:sifre@cluster.mongodb.net        ║
╚══════════════════════════════════════════════════════════════════╝
MONGO_URL: """).strip()

DB_NAME = input("Veritabanı adı (varsayılan: anticca): ").strip() or "anticca"

ADMIN_EMAIL = input("Admin e-posta (varsayılan: admin@anticca.com): ").strip() or "admin@anticca.com"
ADMIN_PASSWORD = getpass.getpass("Admin şifresi (min 8 karakter, büyük harf, rakam, özel karakter): ")


# ══════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def future(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

def past(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

def pid() -> str:
    return f"prod_{uuid.uuid4().hex[:12]}"

def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def generate_user_id() -> str:
    return f"user_{uuid.uuid4().hex[:16]}"

def print_step(step: str):
    print(f"\n{'═'*60}")
    print(f"  ✦ {step}")
    print(f"{'═'*60}")

def print_ok(msg: str):
    print(f"  ✅ {msg}")

def print_skip(msg: str):
    print(f"  ⏭️  {msg} (zaten mevcut, atlandı)")


# ══════════════════════════════════════════════════════════════════
# BAĞLANTI
# ══════════════════════════════════════════════════════════════════

print_step("MongoDB bağlantısı kuruluyor...")

try:
    client = MongoClient(
        MONGO_URL,
        serverSelectionTimeoutMS=8000,
        maxPoolSize=10,
    )
    client.admin.command("ping")
    db = client[DB_NAME]
    print_ok(f"Bağlantı başarılı → Veritabanı: {DB_NAME}")
except ConnectionFailure as e:
    print(f"\n  ❌ BAĞLANTI HATASI: {e}")
    print("  Lütfen MONGO_URL'nizi ve ağ erişiminizi kontrol edin.")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════
# 1. KOLEKSİYONLAR — JSON Schema Validasyonu ile
# ══════════════════════════════════════════════════════════════════

print_step("Koleksiyonlar ve JSON Schema validasyonları oluşturuluyor...")

existing = db.list_collection_names()

COLLECTIONS = {

    "users": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["user_id", "email", "name", "role", "created_at"],
            "properties": {
                "user_id":    {"bsonType": "string", "description": "Benzersiz kullanıcı ID"},
                "email":      {"bsonType": "string", "pattern": "^[^@]+@[^@]+\\.[^@]+$"},
                "name":       {"bsonType": "string", "minLength": 1, "maxLength": 100},
                "role":       {"bsonType": "string", "enum": ["user", "admin", "store_owner"]},
                "phone":      {"bsonType": ["string", "null"]},
                "picture":    {"bsonType": ["string", "null"]},
                "created_at": {"bsonType": "string"},
            }
        }
    },

    "user_sessions": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["session_id", "user_id", "session_token", "expires_at", "created_at"],
            "properties": {
                "session_id":    {"bsonType": "string"},
                "user_id":       {"bsonType": "string"},
                "session_token": {"bsonType": "string"},
                "expires_at":    {"bsonType": "string"},
                "created_at":    {"bsonType": "string"},
            }
        }
    },

    "products": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["product_id", "title", "description", "category", "price", "currency", "status", "approval_status", "created_at"],
            "properties": {
                "product_id":      {"bsonType": "string"},
                "title":           {"bsonType": "object"},
                "description":     {"bsonType": "object"},
                "category":        {"bsonType": "string", "enum": ["watches", "art", "jewelry", "coins", "antiques", "wine", "cars", "memorabilia"]},
                "price":           {"bsonType": "double", "minimum": 0},
                "currency":        {"bsonType": "string", "enum": ["USD", "EUR", "TRY"]},
                "condition":       {"bsonType": ["string", "null"]},
                "images":          {"bsonType": "array"},
                "is_auction":      {"bsonType": "bool"},
                "status":          {"bsonType": "string", "enum": ["active", "sold", "cancelled", "draft", "pending"]},
                "approval_status": {"bsonType": "string", "enum": ["pending", "approved", "rejected"]},
                "featured":        {"bsonType": "bool"},
                "view_count":      {"bsonType": ["int", "double"]},
                "created_at":      {"bsonType": "string"},
            }
        }
    },

    "bids": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["bid_id", "product_id", "user_id", "amount", "created_at"],
            "properties": {
                "bid_id":     {"bsonType": "string"},
                "product_id": {"bsonType": "string"},
                "user_id":    {"bsonType": "string"},
                "amount":     {"bsonType": "double", "minimum": 0},
                "created_at": {"bsonType": "string"},
            }
        }
    },

    "cart_items": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["user_id", "product_id", "quantity", "added_at"],
            "properties": {
                "user_id":    {"bsonType": "string"},
                "product_id": {"bsonType": "string"},
                "quantity":   {"bsonType": "int", "minimum": 1, "maximum": 10},
                "added_at":   {"bsonType": "string"},
            }
        }
    },

    "orders": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["order_id", "user_id", "items", "total", "currency", "status", "payment_status", "created_at"],
            "properties": {
                "order_id":       {"bsonType": "string"},
                "user_id":        {"bsonType": "string"},
                "items":          {"bsonType": "array"},
                "total":          {"bsonType": "double", "minimum": 0},
                "currency":       {"bsonType": "string", "enum": ["USD", "EUR", "TRY"]},
                "status":         {"bsonType": "string", "enum": ["pending", "confirmed", "processing", "shipped", "completed", "cancelled", "refunded"]},
                "payment_status": {"bsonType": "string", "enum": ["pending", "paid", "failed", "refunded"]},
                "created_at":     {"bsonType": "string"},
            }
        }
    },

    "payment_transactions": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["transaction_id", "order_id", "amount", "currency", "status", "created_at"],
            "properties": {
                "transaction_id": {"bsonType": "string"},
                "order_id":       {"bsonType": "string"},
                "session_id":     {"bsonType": ["string", "null"]},
                "amount":         {"bsonType": "double", "minimum": 0},
                "currency":       {"bsonType": "string"},
                "status":         {"bsonType": "string"},
                "provider":       {"bsonType": ["string", "null"]},
                "created_at":     {"bsonType": "string"},
            }
        }
    },

    "stores": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["store_id", "name", "description", "created_at"],
            "properties": {
                "store_id":      {"bsonType": "string"},
                "name":          {"bsonType": "string", "minLength": 1, "maxLength": 100},
                "description":   {"bsonType": "object"},
                "verified":      {"bsonType": ["bool", "null"]},
                "contact_email": {"bsonType": ["string", "null"]},
                "created_at":    {"bsonType": "string"},
            }
        }
    },

    "articles": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["article_id", "title", "content", "author", "published", "created_at"],
            "properties": {
                "article_id": {"bsonType": "string"},
                "title":      {"bsonType": "object"},
                "content":    {"bsonType": "object"},
                "author":     {"bsonType": "string"},
                "published":  {"bsonType": "bool"},
                "slug":       {"bsonType": ["string", "null"]},
                "created_at": {"bsonType": "string"},
            }
        }
    },

    "faq": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["faq_id", "question", "answer", "category", "order"],
            "properties": {
                "faq_id":   {"bsonType": "string"},
                "question": {"bsonType": "object"},
                "answer":   {"bsonType": "object"},
                "category": {"bsonType": "string"},
                "order":    {"bsonType": "int"},
            }
        }
    },

    "categories": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["category_id", "name"],
            "properties": {
                "category_id": {"bsonType": "string"},
                "name":        {"bsonType": "object"},
                "icon":        {"bsonType": ["string", "null"]},
            }
        }
    },

    "watchlist": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["user_id", "product_id", "added_at"],
            "properties": {
                "user_id":    {"bsonType": "string"},
                "product_id": {"bsonType": "string"},
                "added_at":   {"bsonType": "string"},
            }
        }
    },

    "newsletter": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["email", "subscribed_at"],
            "properties": {
                "email":         {"bsonType": "string"},
                "language":      {"bsonType": ["string", "null"]},
                "subscribed_at": {"bsonType": "string"},
                "active":        {"bsonType": ["bool", "null"]},
            }
        }
    },
}

for col_name, schema in COLLECTIONS.items():
    if col_name in existing:
        # Güncelle validasyon
        try:
            db.command("collMod", col_name, validator=schema, validationLevel="moderate")
            print_ok(f"{col_name:25} → validasyon güncellendi")
        except OperationFailure as e:
            print(f"  ⚠️  {col_name}: {e}")
    else:
        db.create_collection(col_name, validator=schema, validationLevel="moderate", validationAction="warn")
        print_ok(f"{col_name:25} → koleksiyon oluşturuldu")


# ══════════════════════════════════════════════════════════════════
# 2. INDEX'LER — Performans + Veri Bütünlüğü
# ══════════════════════════════════════════════════════════════════

print_step("Index'ler oluşturuluyor...")

indexes = {
    "users": [
        ([("email", ASCENDING)],       {"unique": True,  "name": "idx_users_email_unique"}),
        ([("user_id", ASCENDING)],     {"unique": True,  "name": "idx_users_user_id_unique"}),
        ([("role", ASCENDING)],        {"name": "idx_users_role"}),
        ([("created_at", DESCENDING)], {"name": "idx_users_created_at"}),
    ],
    "user_sessions": [
        ([("session_token", ASCENDING)], {"unique": True, "name": "idx_sessions_token_unique"}),
        ([("user_id", ASCENDING)],       {"name": "idx_sessions_user_id"}),
        ([("expires_at", ASCENDING)],    {"name": "idx_sessions_expires_at", "expireAfterSeconds": 0}),
    ],
    "products": [
        ([("product_id", ASCENDING)],    {"unique": True, "name": "idx_products_id_unique"}),
        ([("category", ASCENDING)],      {"name": "idx_products_category"}),
        ([("status", ASCENDING)],        {"name": "idx_products_status"}),
        ([("approval_status", ASCENDING)], {"name": "idx_products_approval"}),
        ([("is_auction", ASCENDING)],    {"name": "idx_products_is_auction"}),
        ([("featured", ASCENDING)],      {"name": "idx_products_featured"}),
        ([("store_id", ASCENDING)],      {"name": "idx_products_store_id"}),
        ([("created_at", DESCENDING)],   {"name": "idx_products_created_at"}),
        ([("auction_end", ASCENDING)],   {"name": "idx_products_auction_end"}),
        ([("price", ASCENDING)],         {"name": "idx_products_price_asc"}),
        ([("price", DESCENDING)],        {"name": "idx_products_price_desc"}),
        # Bileşik index — filtreleme + sıralama
        ([("status", ASCENDING), ("approval_status", ASCENDING), ("is_auction", ASCENDING)],
         {"name": "idx_products_compound_filter"}),
        ([("status", ASCENDING), ("featured", ASCENDING), ("created_at", DESCENDING)],
         {"name": "idx_products_featured_listing"}),
        # Full-text arama
        ([("title.tr", TEXT), ("title.en", TEXT), ("title.it", TEXT)],
         {"name": "idx_products_text_search", "default_language": "none"}),
    ],
    "bids": [
        ([("bid_id", ASCENDING)],                              {"unique": True, "name": "idx_bids_id_unique"}),
        ([("product_id", ASCENDING)],                         {"name": "idx_bids_product_id"}),
        ([("user_id", ASCENDING)],                            {"name": "idx_bids_user_id"}),
        ([("product_id", ASCENDING), ("amount", DESCENDING)], {"name": "idx_bids_product_amount"}),
        ([("product_id", ASCENDING), ("created_at", DESCENDING)], {"name": "idx_bids_product_time"}),
    ],
    "cart_items": [
        ([("user_id", ASCENDING), ("product_id", ASCENDING)],
         {"unique": True, "name": "idx_cart_user_product_unique"}),
        ([("user_id", ASCENDING)], {"name": "idx_cart_user_id"}),
    ],
    "orders": [
        ([("order_id", ASCENDING)],   {"unique": True, "name": "idx_orders_id_unique"}),
        ([("user_id", ASCENDING)],    {"name": "idx_orders_user_id"}),
        ([("session_id", ASCENDING)], {"name": "idx_orders_session_id"}),
        ([("status", ASCENDING)],     {"name": "idx_orders_status"}),
        ([("payment_status", ASCENDING)], {"name": "idx_orders_payment_status"}),
        ([("created_at", DESCENDING)],    {"name": "idx_orders_created_at"}),
    ],
    "payment_transactions": [
        ([("transaction_id", ASCENDING)], {"unique": True, "name": "idx_payments_id_unique"}),
        ([("session_id", ASCENDING)],     {"name": "idx_payments_session_id"}),
        ([("order_id", ASCENDING)],       {"name": "idx_payments_order_id"}),
        ([("status", ASCENDING)],         {"name": "idx_payments_status"}),
    ],
    "stores": [
        ([("store_id", ASCENDING)], {"unique": True, "name": "idx_stores_id_unique"}),
        ([("verified", ASCENDING)], {"name": "idx_stores_verified"}),
        ([("name", ASCENDING)],     {"name": "idx_stores_name"}),
    ],
    "articles": [
        ([("article_id", ASCENDING)],    {"unique": True, "name": "idx_articles_id_unique"}),
        ([("slug", ASCENDING)],          {"unique": True, "sparse": True, "name": "idx_articles_slug_unique"}),
        ([("published", ASCENDING)],     {"name": "idx_articles_published"}),
        ([("created_at", DESCENDING)],   {"name": "idx_articles_created_at"}),
        ([("category", ASCENDING)],      {"name": "idx_articles_category"}),
    ],
    "faq": [
        ([("faq_id", ASCENDING)], {"unique": True, "name": "idx_faq_id_unique"}),
        ([("order", ASCENDING)],  {"name": "idx_faq_order"}),
        ([("category", ASCENDING)], {"name": "idx_faq_category"}),
    ],
    "categories": [
        ([("category_id", ASCENDING)], {"unique": True, "name": "idx_categories_id_unique"}),
    ],
    "watchlist": [
        ([("user_id", ASCENDING), ("product_id", ASCENDING)],
         {"unique": True, "name": "idx_watchlist_user_product_unique"}),
        ([("user_id", ASCENDING)],    {"name": "idx_watchlist_user_id"}),
        ([("product_id", ASCENDING)], {"name": "idx_watchlist_product_id"}),
    ],
    "newsletter": [
        ([("email", ASCENDING)],        {"unique": True, "name": "idx_newsletter_email_unique"}),
        ([("active", ASCENDING)],       {"name": "idx_newsletter_active"}),
        ([("subscribed_at", ASCENDING)], {"name": "idx_newsletter_subscribed_at"}),
    ],
}

total_indexes = 0
for col_name, col_indexes in indexes.items():
    col = db[col_name]
    existing_idx_names = [i["name"] for i in col.list_indexes()]
    for keys, opts in col_indexes:
        idx_name = opts.get("name", "unnamed")
        if idx_name not in existing_idx_names:
            col.create_index(keys, **opts)
            print_ok(f"{col_name:25}.{idx_name}")
            total_indexes += 1
        else:
            pass  # Zaten var

print_ok(f"Toplam {total_indexes} yeni index oluşturuldu")


# ══════════════════════════════════════════════════════════════════
# 3. SEED VERİLERİ
# ══════════════════════════════════════════════════════════════════

print_step("Başlangıç verileri yükleniyor...")


# ── Kategoriler ──────────────────────────────────────────────────
if db.categories.count_documents({}) == 0:
    categories = [
        {"category_id": "watches",      "name": {"tr": "Saatler",       "en": "Watches",    "it": "Orologi"},    "icon": "⌚"},
        {"category_id": "art",          "name": {"tr": "Sanat",         "en": "Art",        "it": "Arte"},       "icon": "🎨"},
        {"category_id": "jewelry",      "name": {"tr": "Mücevher",      "en": "Jewelry",    "it": "Gioielli"},   "icon": "💎"},
        {"category_id": "coins",        "name": {"tr": "Sikkeler",      "en": "Coins",      "it": "Monete"},     "icon": "🪙"},
        {"category_id": "antiques",     "name": {"tr": "Antikalar",     "en": "Antiques",   "it": "Antichità"},  "icon": "🏺"},
        {"category_id": "wine",         "name": {"tr": "Şarap",         "en": "Wine",       "it": "Vino"},       "icon": "🍷"},
        {"category_id": "cars",         "name": {"tr": "Otomobiller",   "en": "Cars",       "it": "Auto"},       "icon": "🚗"},
        {"category_id": "memorabilia",  "name": {"tr": "Memorabilia",   "en": "Memorabilia","it": "Memorabilia"},"icon": "🏆"},
    ]
    db.categories.insert_many(categories)
    print_ok(f"Kategoriler: {len(categories)} adet eklendi")
else:
    print_skip("Kategoriler")


# ── Mağazalar ─────────────────────────────────────────────────────
if db.stores.count_documents({}) == 0:
    stores = [
        {
            "store_id": "store_kronos01",
            "name": "Kronos Antik Saatler",
            "description": {
                "tr": "Türkiye'nin önde gelen antik saat ve lüks zaman parçaları uzmanı. 30 yıllık deneyim.",
                "en": "Turkey's leading antique watch and luxury timepiece specialist. 30 years of expertise.",
                "it": "Lo specialista leader in Turchia per orologi antichi. 30 anni di esperienza.",
            },
            "logo": "https://images.pexels.com/photos/2113994/pexels-photo-2113994.jpeg?auto=compress&cs=tinysrgb&w=200",
            "contact_email": "info@kronosantik.com",
            "address": "Nişantaşı, İstanbul",
            "phone": "+90 212 555 0001",
            "website": "https://kronosantik.com",
            "verified": True,
            "created_at": now(),
        },
        {
            "store_id": "store_galeri02",
            "name": "Galeri İstanbul",
            "description": {
                "tr": "Çağdaş ve klasik sanat eserlerinin buluşma noktası. 1987'den beri sanat dünyasında.",
                "en": "Meeting point for contemporary and classical art. In the art world since 1987.",
                "it": "Punto d'incontro per l'arte contemporanea e classica. Nel mondo dell'arte dal 1987.",
            },
            "logo": "https://images.pexels.com/photos/3004909/pexels-photo-3004909.jpeg?auto=compress&cs=tinysrgb&w=200",
            "contact_email": "info@galeriistanbul.com",
            "address": "Beyoğlu, İstanbul",
            "phone": "+90 212 555 0002",
            "website": "https://galeriistanbul.com",
            "verified": True,
            "created_at": now(),
        },
        {
            "store_id": "store_heritage03",
            "name": "Miras Koleksiyonları",
            "description": {
                "tr": "Nadir sikkeler, antika mobilyalar ve tarihi eserler konusunda uzmanlaşmış güvenilir koleksiyon evi.",
                "en": "Trusted collection house specializing in rare coins, antique furniture, and historical artifacts.",
                "it": "Casa di collezioni affidabile specializzata in monete rare e manufatti storici.",
            },
            "logo": "https://images.pexels.com/photos/6044266/pexels-photo-6044266.jpeg?auto=compress&cs=tinysrgb&w=200",
            "contact_email": "info@miraskoleksiyon.com",
            "address": "Kadıköy, İstanbul",
            "phone": "+90 216 555 0003",
            "website": "https://miraskoleksiyon.com",
            "verified": True,
            "created_at": now(),
        },
        {
            "store_id": "store_vinoantik04",
            "name": "Vino Antik",
            "description": {
                "tr": "Dünya'nın en nadir ve değerli şaraplarının koleksiyonu. Özel şarap müzayedesinde uzman.",
                "en": "Collection of the world's rarest and most valuable wines. Expert in private wine auctions.",
                "it": "Collezione dei vini più rari e preziosi del mondo. Esperto in aste private di vino.",
            },
            "logo": "https://images.pexels.com/photos/2912108/pexels-photo-2912108.jpeg?auto=compress&cs=tinysrgb&w=200",
            "contact_email": "info@vinoantik.com",
            "address": "Bebek, İstanbul",
            "phone": "+90 212 555 0004",
            "website": "https://vinoantik.com",
            "verified": True,
            "created_at": now(),
        },
    ]
    db.stores.insert_many(stores)
    print_ok(f"Mağazalar: {len(stores)} adet eklendi")
else:
    print_skip("Mağazalar")


# ── Ürünler ────────────────────────────────────────────────────────
if db.products.count_documents({}) == 0:
    products = [
        # ── SAAT ────────────────────────────────────────────
        {
            "product_id": pid(),
            "title": {"tr": "Patek Philippe Nautilus 5711/1A-010", "en": "Patek Philippe Nautilus 5711/1A-010", "it": "Patek Philippe Nautilus 5711/1A-010"},
            "description": {
                "tr": "Orijinal kutu ve belgeleriyle kusursuz durumda Patek Philippe Nautilus 5711/1A-010. Paslanmaz çelik kasa, mavi kadran. Seri numarası doğrulanmış.",
                "en": "Pristine Patek Philippe Nautilus 5711/1A-010 with original box and papers. Stainless steel case, blue dial. Serial number verified.",
                "it": "Patek Philippe Nautilus 5711/1A-010 in condizioni perfette con scatola e documenti originali.",
            },
            "category": "watches", "price": 185000.00, "currency": "USD",
            "images": [
                "https://images.pexels.com/photos/16886383/pexels-photo-16886383.jpeg?auto=compress&cs=tinysrgb&w=800",
                "https://images.pexels.com/photos/2113994/pexels-photo-2113994.jpeg?auto=compress&cs=tinysrgb&w=800",
            ],
            "condition": "excellent",
            "provenance": {"tr": "Özel Avrupa koleksiyonu, 2019'da edinildi", "en": "Private European collection, acquired 2019", "it": "Collezione privata europea, acquisito 2019"},
            "investment_perspective": {"tr": "Son 5 yılda %45 değer artışı. Referans model üretimden kaldırıldı.", "en": "45% value appreciation in last 5 years. Reference discontinued.", "it": "Apprezzamento del 45% negli ultimi 5 anni."},
            "condition_report": {"tr": "Kadran orijinal. Kasa çizik yok. Servise alınmamış.", "en": "Original dial. Case scratch-free. Unpolished.", "it": "Quadrante originale. Nessun graffio."},
            "certification_docs": [{"type": "Manufacturer Certificate", "year": 2019}],
            "is_auction": False, "status": "active", "approval_status": "approved",
            "featured": True, "store_id": "store_kronos01",
            "created_at": now(), "view_count": 0,
        },
        {
            "product_id": pid(),
            "title": {"tr": "Rolex Daytona Paul Newman 6239", "en": "Rolex Daytona Paul Newman 6239", "it": "Rolex Daytona Paul Newman 6239"},
            "description": {
                "tr": "Orijinal Paul Newman kadranıyla Rolex Daytona 6239. Koleksiyoncuların en çok aradığı model. Tam set, servis kayıtları mevcut.",
                "en": "Rolex Daytona 6239 with original Paul Newman dial. Most sought-after by collectors. Full set with service records.",
                "it": "Rolex Daytona 6239 con quadrante Paul Newman originale. Full set.",
            },
            "category": "watches", "price": 350000.00, "currency": "USD",
            "images": [
                "https://images.pexels.com/photos/2113994/pexels-photo-2113994.jpeg?auto=compress&cs=tinysrgb&w=800",
            ],
            "condition": "excellent",
            "provenance": {"tr": "İtalyan özel koleksiyondan, 1998'de satın alındı", "en": "From Italian private collection, purchased 1998", "it": "Da collezione privata italiana"},
            "is_auction": True,
            "auction_start": now(), "auction_end": future(4),
            "starting_bid": 280000.00, "reserve_price": 330000.00,
            "current_bid": 305000.00, "bid_count": 6, "min_increment": 5000.00,
            "status": "active", "approval_status": "approved", "featured": True,
            "store_id": "store_kronos01", "created_at": past(1), "view_count": 0,
        },
        # ── ARABA ────────────────────────────────────────────
        {
            "product_id": pid(),
            "title": {"tr": "1955 Mercedes-Benz 300SL Gullwing", "en": "1955 Mercedes-Benz 300SL Gullwing", "it": "1955 Mercedes-Benz 300SL Gullwing"},
            "description": {
                "tr": "Eşleşen numaralar, Silver Blue Metallic renkte tamamen restore edilmiş 300SL Gullwing. FIA klasik araç belgesi mevcut.",
                "en": "Matching numbers, fully restored 300SL Gullwing in Silver Blue Metallic. FIA classic car certificate available.",
                "it": "Numeri corrispondenti, 300SL Gullwing completamente restaurata in Silver Blue Metallic.",
            },
            "category": "cars", "price": 1450000.00, "currency": "USD",
            "images": [
                "https://images.pexels.com/photos/16560119/pexels-photo-16560119.jpeg?auto=compress&cs=tinysrgb&w=800",
            ],
            "condition": "restored",
            "provenance": {"tr": "Özel Alman koleksiyonu, 1970'lerden bu yana tek sahibi", "en": "Private German collection, single owner since 1970s", "it": "Collezione privata tedesca"},
            "investment_perspective": {"tr": "Klasik otomobil piyasasında istikrarlı değer artışı. Gullwing modelleri yıllık %8-12 değerleniyor.", "en": "Stable appreciation. Gullwing models appreciate 8-12% annually.", "it": "Stabile apprezzamento del 8-12% annuo."},
            "is_auction": True,
            "auction_start": now(), "auction_end": future(7),
            "starting_bid": 1200000.00, "reserve_price": 1400000.00,
            "current_bid": 1250000.00, "bid_count": 3, "min_increment": 25000.00,
            "status": "active", "approval_status": "approved", "featured": True,
            "store_id": "store_heritage03", "created_at": past(2), "view_count": 0,
        },
        # ── SANAT ────────────────────────────────────────────
        {
            "product_id": pid(),
            "title": {"tr": "Banksy - Balonlu Kız (İmzalı Baskı)", "en": "Banksy - Girl with Balloon (Signed Print)", "it": "Banksy - Ragazza con Palloncino"},
            "description": {
                "tr": "Doğrulanmış Banksy serigrafi baskısı, 150 adetlik edisyon. Pest Control sertifikası ve COA belgesi mevcut.",
                "en": "Authenticated Banksy screen print, edition of 150. Pest Control certificate and COA included.",
                "it": "Serigrafia autenticata di Banksy, edizione di 150. Certificato Pest Control incluso.",
            },
            "category": "art", "price": 420000.00, "currency": "USD",
            "images": [
                "https://images.pexels.com/photos/4046718/pexels-photo-4046718.jpeg?auto=compress&cs=tinysrgb&w=800",
            ],
            "condition": "mint",
            "provenance": {"tr": "Londra özel koleksiyonundan, 2008 Sotheby's müzayedesinden alındı", "en": "From private London collection, purchased at 2008 Sotheby's auction", "it": "Da collezione privata londinese, acquistato all'asta Sotheby's 2008"},
            "certification_docs": [{"type": "Pest Control Certificate", "year": 2008}],
            "is_auction": True,
            "auction_start": now(), "auction_end": future(5),
            "starting_bid": 350000.00, "reserve_price": 400000.00,
            "current_bid": 380000.00, "bid_count": 8, "min_increment": 10000.00,
            "status": "active", "approval_status": "approved", "featured": True,
            "store_id": "store_galeri02", "created_at": past(1), "view_count": 0,
        },
        # ── SİKKE ────────────────────────────────────────────
        {
            "product_id": pid(),
            "title": {"tr": "1794 Akan Saçlı Gümüş Dolar", "en": "1794 Flowing Hair Silver Dollar", "it": "1794 Dollaro d'Argento Flowing Hair"},
            "description": {
                "tr": "ABD Darphanesi tarafından basılan ilk gümüş dolarlardan biri. PCGS VF-35 derecelendirmesi. Dünya çapında bilinen en değerli sikkelerden.",
                "en": "One of the first silver dollars struck by the US Mint. PCGS graded VF-35. One of the most valuable coins worldwide.",
                "it": "Uno dei primi dollari d'argento della Zecca USA. PCGS VF-35.",
            },
            "category": "coins", "price": 5200000.00, "currency": "USD",
            "images": [
                "https://images.pexels.com/photos/30895543/pexels-photo-30895543.jpeg?auto=compress&cs=tinysrgb&w=800",
            ],
            "condition": "very_fine",
            "provenance": {"tr": "ABD özel koleksiyonundan, aile mirasından gelen parça", "en": "From private US collection, family heirloom piece", "it": "Da collezione privata USA, pezzo di famiglia"},
            "investment_perspective": {"tr": "Nadir sikke piyasasında en yüksek değer artış potansiyeli. Tarihi açıdan eşsiz.", "en": "Highest appreciation potential in rare coin market. Historically unique.", "it": "Massimo potenziale nel mercato delle monete rare."},
            "certification_docs": [{"type": "PCGS Certificate", "grade": "VF-35", "year": 2020}],
            "is_auction": False, "status": "active", "approval_status": "approved",
            "featured": True, "store_id": "store_heritage03",
            "created_at": past(3), "view_count": 0,
        },
        # ── MÜCEVHER ─────────────────────────────────────────
        {
            "product_id": pid(),
            "title": {"tr": "Cartier Art Deco Elmas Bileklik", "en": "Cartier Art Deco Diamond Bracelet", "it": "Bracciale Cartier Art Deco con Diamanti"},
            "description": {
                "tr": "Yaklaşık 1925 Cartier platin ve elmas Art Deco bileklik. Toplam 18.5 karat elmas. Cartier arşiv belgesiyle desteklenmiş.",
                "en": "Circa 1925 Cartier platinum and diamond Art Deco bracelet. Total 18.5 carats. Supported by Cartier archive document.",
                "it": "Bracciale Art Deco Cartier in platino e diamanti, circa 1925. 18,5 carati totali.",
            },
            "category": "jewelry", "price": 890000.00, "currency": "USD",
            "images": [
                "https://images.pexels.com/photos/16886383/pexels-photo-16886383.jpeg?auto=compress&cs=tinysrgb&w=800",
            ],
            "condition": "excellent",
            "provenance": {"tr": "İsviçreli özel koleksiyoncudan, Christie's 2003 müzayedesinde satın alındı", "en": "From Swiss private collector, purchased Christie's 2003 auction", "it": "Da collezionista privato svizzero"},
            "certification_docs": [{"type": "GIA Certificate"}, {"type": "Cartier Archive Document"}],
            "is_auction": True,
            "auction_start": now(), "auction_end": future(3),
            "starting_bid": 750000.00, "reserve_price": 850000.00,
            "current_bid": 810000.00, "bid_count": 12, "min_increment": 15000.00,
            "status": "active", "approval_status": "approved", "featured": True,
            "store_id": "store_kronos01", "created_at": past(1), "view_count": 0,
        },
        # ── ANTİKA ───────────────────────────────────────────
        {
            "product_id": pid(),
            "title": {"tr": "18. Yüzyıl Ming Hanedanı Vazosu", "en": "18th Century Ming Dynasty Vase", "it": "Vaso della Dinastia Ming del XVIII Secolo"},
            "description": {
                "tr": "El boyaması mavi-beyaz dekorasyonlu nadide Ming Hanedanı porselen vazo. Britanya Müzesi uzmanlarınca doğrulanmış.",
                "en": "Exquisite Ming Dynasty porcelain vase with hand-painted blue and white decoration. Verified by British Museum experts.",
                "it": "Squisito vaso in porcellana della Dinastia Ming. Verificato da esperti del British Museum.",
            },
            "category": "antiques", "price": 320000.00, "currency": "USD",
            "images": [
                "https://images.pexels.com/photos/4046718/pexels-photo-4046718.jpeg?auto=compress&cs=tinysrgb&w=800",
            ],
            "condition": "good",
            "provenance": {"tr": "İngiliz özel mülkünden, 1920'lerden bu yana aynı aile", "en": "From English private estate, same family since 1920s", "it": "Da proprietà privata inglese"},
            "is_auction": False, "status": "active", "approval_status": "approved",
            "featured": False, "store_id": "store_heritage03",
            "created_at": past(5), "view_count": 0,
        },
        # ── ŞARAP ────────────────────────────────────────────
        {
            "product_id": pid(),
            "title": {"tr": "1961 Pétrus - Orijinal Ahşap Sandık (6 Şişe)", "en": "1961 Pétrus - Original Wooden Case (6 Bottles)", "it": "1961 Pétrus - Cassa di Legno Originale (6 Bottiglie)"},
            "description": {
                "tr": "Yüzyılın en iyi pomerol üzümünden üretilen 1961 Pétrus. Orijinal ahşap sandık, mükemmel depolama koşulları. Parker 100 puan.",
                "en": "1961 Pétrus from the best pomerol harvest of the century. Original wooden case, perfect storage. Parker 100 points.",
                "it": "1961 Pétrus dalla migliore vendemmia del secolo. Cassa originale. Parker 100 punti.",
            },
            "category": "wine", "price": 95000.00, "currency": "USD",
            "images": [
                "https://images.pexels.com/photos/2912108/pexels-photo-2912108.jpeg?auto=compress&cs=tinysrgb&w=800",
            ],
            "condition": "excellent",
            "provenance": {"tr": "Bordeaux özel mahzeninden, profesyonel iklim kontrollü depolama", "en": "From private Bordeaux cellar, professional climate-controlled storage", "it": "Da cantina privata di Bordeaux"},
            "is_auction": True,
            "auction_start": now(), "auction_end": future(6),
            "starting_bid": 75000.00, "reserve_price": 90000.00,
            "current_bid": 82000.00, "bid_count": 5, "min_increment": 2000.00,
            "status": "active", "approval_status": "approved", "featured": False,
            "store_id": "store_vinoantik04", "created_at": past(2), "view_count": 0,
        },
        # ── MEMORABİLİA ──────────────────────────────────────
        {
            "product_id": pid(),
            "title": {"tr": "Michael Jordan 1998 NBA Finalleri İmzalı Forma", "en": "Michael Jordan 1998 NBA Finals Signed Jersey", "it": "Canotta Firmata Michael Jordan NBA Finals 1998"},
            "description": {
                "tr": "Son şampiyonluk sezonundan orijinal Michael Jordan imzalı Chicago Bulls forması. JSA ve PSA/DNA sertifikalı.",
                "en": "Original Michael Jordan signed Chicago Bulls jersey from his last championship season. JSA and PSA/DNA certified.",
                "it": "Canotta originale firmata di Michael Jordan. Certificata JSA e PSA/DNA.",
            },
            "category": "memorabilia", "price": 48000.00, "currency": "USD",
            "images": [
                "https://images.pexels.com/photos/6044266/pexels-photo-6044266.jpeg?auto=compress&cs=tinysrgb&w=800",
            ],
            "condition": "excellent",
            "provenance": {"tr": "Eski NBA oyuncusundan, doğrudan teslim alındı", "en": "From former NBA player, directly acquired", "it": "Da ex giocatore NBA"},
            "certification_docs": [{"type": "JSA Certificate"}, {"type": "PSA/DNA Certificate"}],
            "is_auction": False, "status": "active", "approval_status": "approved",
            "featured": False, "store_id": "store_heritage03",
            "created_at": past(4), "view_count": 0,
        },
    ]
    db.products.insert_many(products)
    print_ok(f"Ürünler: {len(products)} adet eklendi")
else:
    print_skip("Ürünler")


# ── Makaleler ─────────────────────────────────────────────────────
if db.articles.count_documents({}) == 0:
    articles = [
        {
            "article_id": "art_invest01",
            "title": {"tr": "Yatırım Olarak Koleksiyon Saatler: 2025 Rehberi", "en": "Collectible Watches as Investment: 2025 Guide", "it": "Orologi da Collezione come Investimento: Guida 2025"},
            "excerpt": {"tr": "Koleksiyon saatlerinin değerinin neden arttığı ve hangi modellerin en iyi yatırım olduğu hakkında kapsamlı bir rehber.", "en": "A comprehensive guide on why collectible watches appreciate and which models are the best investments.", "it": "Una guida completa sugli orologi da collezione come investimento."},
            "content": {"tr": "Koleksiyon saatleri, son on yılda en yüksek getiri sağlayan varlık sınıflarından biri olmuştur. Patek Philippe, Rolex ve AP gibi markalar yıllık ortalama %15-20 değer artışı göstermektedir.", "en": "Collectible watches have been one of the highest-returning asset classes over the past decade. Brands like Patek Philippe, Rolex and AP show 15-20% annual appreciation.", "it": "Gli orologi da collezione sono stati una delle classi di attivi con il rendimento più alto."},
            "category": "yatırım", "author": "Dr. Ahmet Yılmaz",
            "featured_image": "https://images.pexels.com/photos/2113994/pexels-photo-2113994.jpeg?auto=compress&cs=tinysrgb&w=800",
            "published": True, "slug": "yatirim-olarak-koleksiyon-saatler-2025", "created_at": now(),
        },
        {
            "article_id": "art_ottoman02",
            "title": {"tr": "Osmanlı Dönemi Antikalarının Yükselen Değeri", "en": "The Rising Value of Ottoman Period Antiques", "it": "Il Valore Crescente delle Antichità Ottomane"},
            "excerpt": {"tr": "Uluslararası piyasalarda Osmanlı dönemi eserlerine olan talebin artışı ve değerlendirme kriterleri.", "en": "The increasing demand for Ottoman period artifacts in international markets and valuation criteria.", "it": "La crescente domanda di manufatti ottomani nei mercati internazionali."},
            "content": {"tr": "Osmanlı İmparatorluğu'nun altı yüzyıllık tarihinden kalan eserler, uluslararası müzayede evlerinde giderek artan bir ilgiyle karşılanmaktadır. Christie's ve Sotheby's'deki Osmanlı eserleri satışları son 5 yılda 3 kat artış göstermiştir.", "en": "Artifacts from the Ottoman Empire's six-century history are meeting increasing interest at international auction houses.", "it": "I manufatti dell'Impero Ottomano stanno incontrando un crescente interesse."},
            "category": "kültür", "author": "Prof. Zeynep Kaya",
            "featured_image": "https://images.pexels.com/photos/6044266/pexels-photo-6044266.jpeg?auto=compress&cs=tinysrgb&w=800",
            "published": True, "slug": "osmanli-donemi-antikalarinin-yukselen-degeri", "created_at": past(3),
        },
        {
            "article_id": "art_contemp03",
            "title": {"tr": "Çağdaş Sanat Piyasası: 2025 Trendleri", "en": "Contemporary Art Market: 2025 Trends", "it": "Mercato dell'Arte Contemporanea: Tendenze 2025"},
            "excerpt": {"tr": "Dijital sanat, NFT sonrası dönem ve fiziksel eserlerin yeniden yükselişi.", "en": "Digital art, post-NFT era and the re-rise of physical works.", "it": "Arte digitale e la rinascita delle opere fisiche."},
            "content": {"tr": "2025 yılı, çağdaş sanat piyasası için önemli dönüşümlerin yaşandığı bir dönem olmaktadır. NFT patlamasının ardından koleksiyoncular yeniden fiziksel eserlere yönelmiş durumda.", "en": "2025 is a period of significant transformations. After the NFT boom, collectors are returning to physical works.", "it": "Il 2025 è un periodo di significative trasformazioni."},
            "category": "sanat", "author": "Elif Demir",
            "featured_image": "https://images.pexels.com/photos/3004909/pexels-photo-3004909.jpeg?auto=compress&cs=tinysrgb&w=800",
            "published": True, "slug": "cagdas-sanat-piyasasi-2025-trendleri", "created_at": past(7),
        },
        {
            "article_id": "art_coins04",
            "title": {"tr": "Nadir Sikkelerin Büyüleyici Tarihi", "en": "The Fascinating History of Rare Coins", "it": "L'Affascinante Storia delle Monete Rare"},
            "excerpt": {"tr": "Antik çağlardan günümüze, sikkelerin tarihi yolculuğu ve koleksiyon değeri.", "en": "The historical journey of coins from ancient times and their collection value.", "it": "Il viaggio storico delle monete dall'antichità."},
            "content": {"tr": "Sikke koleksiyonculuğu, insanlık tarihinin en eski hobilerinden biridir. İlk sikkeler MÖ 7. yüzyılda Lydia'da basılmış olup bugün bazı örnekleri milyonlarca dolara işlem görmektedir.", "en": "Coin collecting is one of the oldest hobbies in human history. The first coins were struck in Lydia in the 7th century BC.", "it": "Il collezionismo di monete è uno degli hobby più antichi."},
            "category": "koleksiyon", "author": "Mehmet Öztürk",
            "featured_image": "https://images.pexels.com/photos/30895543/pexels-photo-30895543.jpeg?auto=compress&cs=tinysrgb&w=800",
            "published": True, "slug": "nadir-sikkelerin-buyuleyici-tarihi", "created_at": past(14),
        },
    ]
    db.articles.insert_many(articles)
    print_ok(f"Makaleler: {len(articles)} adet eklendi")
else:
    print_skip("Makaleler")


# ── SSS (FAQ) ─────────────────────────────────────────────────────
if db.faq.count_documents({}) == 0:
    faq_items = [
        {"faq_id": "faq_01", "order": 1, "category": "genel",
         "question": {"tr": "ANTICCA'da nasıl alış yapabilirim?", "en": "How can I purchase on ANTICCA?", "it": "Come posso acquistare su ANTICCA?"},
         "answer":   {"tr": "Hesap oluşturun, direkt satış ürünlerini sepete ekleyin veya müzayedeye teklif verin. Ödeme Stripe güvencesiyle gerçekleşir.", "en": "Create an account, add direct products to cart or bid on auctions. Payments are secured by Stripe.", "it": "Crea un account, aggiungi al carrello o fai offerte. I pagamenti sono protetti da Stripe."}},
        {"faq_id": "faq_02", "order": 2, "category": "müzayede",
         "question": {"tr": "Müzayede sistemi nasıl çalışıyor?", "en": "How does the auction system work?", "it": "Come funziona il sistema d'asta?"},
         "answer":   {"tr": "Müzayedeler belirlenmiş süre boyunca aktif kalır. Anti-sniping özelliği son dakika tekliflerinde süreyi 5 dakika uzatır. Otomatik teklif sistemi mevcuttur.", "en": "Auctions remain active for a set period. Anti-sniping extends time by 5 min for last-minute bids. Auto-bid available.", "it": "Le aste rimangono attive per un periodo prestabilito con sistema anti-sniping."}},
        {"faq_id": "faq_03", "order": 3, "category": "ödeme",
         "question": {"tr": "Hangi ödeme yöntemlerini kabul ediyorsunuz?", "en": "What payment methods do you accept?", "it": "Quali metodi di pagamento accettate?"},
         "answer":   {"tr": "Stripe ile uluslararası kredi/banka kartı ve banka havalesi kabul edilmektedir. Tüm işlemler 256-bit SSL ile korunmaktadır.", "en": "Stripe international credit/debit card and bank transfer. All transactions protected with 256-bit SSL.", "it": "Stripe carta internazionale e bonifico bancario. SSL 256-bit."}},
        {"faq_id": "faq_04", "order": 4, "category": "ödeme",
         "question": {"tr": "Komisyon oranı nedir?", "en": "What is the commission rate?", "it": "Qual è la percentuale di commissione?"},
         "answer":   {"tr": "Alıcı komisyonu %5, satıcı komisyonu %8-15 (ürün kategorisine göre değişir). Detaylar Komisyon Politikası sayfasında.", "en": "Buyer commission 5%, seller commission 8-15% depending on category. Details on Commission Policy page.", "it": "Commissione acquirente 5%, venditore 8-15%."}},
        {"faq_id": "faq_05", "order": 5, "category": "iade",
         "question": {"tr": "Ürün iadesi mümkün mü?", "en": "Is product return possible?", "it": "È possibile il reso del prodotto?"},
         "answer":   {"tr": "Direkt satışlarda teslimat tarihinden itibaren 14 gün içinde iade mümkündür. Müzayedeler kesin satış olup iade kabul edilmez.", "en": "Direct sales: 14 days return from delivery date. Auctions are final sale, non-returnable.", "it": "Vendite dirette: 14 giorni. Aste: vendita definitiva."}},
        {"faq_id": "faq_06", "order": 6, "category": "güvenlik",
         "question": {"tr": "Ürünlerin gerçekliği nasıl doğrulanıyor?", "en": "How is product authenticity verified?", "it": "Come viene verificata l'autenticità?"},
         "answer":   {"tr": "Tüm ürünler alanında uzman değerlendirici ekibimizce incelenir. Gerektiğinde bağımsız üçüncü taraf ekspertiz talep edilir. Sahtecilik tespiti halinde tam iade yapılır.", "en": "All products are examined by our expert team. Independent third-party appraisal when needed. Full refund if forgery detected.", "it": "Tutti i prodotti sono esaminati dai nostri esperti. Rimborso completo in caso di falso."}},
        {"faq_id": "faq_07", "order": 7, "category": "kargo",
         "question": {"tr": "Kargo ve sigorta nasıl yapılıyor?", "en": "How is shipping and insurance handled?", "it": "Come vengono gestiti spedizione e assicurazione?"},
         "answer":   {"tr": "Tüm ürünler özel ambalajlanarak, ürün değerinin %110'u oranında sigortalı ve takipli kargo ile gönderilir. Uluslararası gönderimler gümrük işlemleriyle birlikte yapılır.", "en": "All items shipped with special packaging, insured at 110% of value, with tracking. International shipments include customs handling.", "it": "Tutti i prodotti imballati specialmente, assicurati al 110% del valore."}},
        {"faq_id": "faq_08", "order": 8, "category": "mağaza",
         "question": {"tr": "Mağaza olarak nasıl başvurabilirim?", "en": "How can I apply as a store?", "it": "Come posso candidarmi come negozio?"},
         "answer":   {"tr": "basvuru@anticca.com adresine mağaza adı, iletişim bilgileri, koleksiyon alanı ve referanslarınızı içeren detaylı bilgilerinizi gönderin. Başvurular 5 iş günü içinde değerlendirilir.", "en": "Send store name, contact info, collection area and references to apply@anticca.com. Applications reviewed within 5 business days.", "it": "Inviate i dettagli a apply@anticca.com. Risposta entro 5 giorni lavorativi."}},
    ]
    db.faq.insert_many(faq_items)
    print_ok(f"SSS: {len(faq_items)} soru eklendi")
else:
    print_skip("SSS (FAQ)")


# ══════════════════════════════════════════════════════════════════
# 4. ADMIN KULLANICISI
# ══════════════════════════════════════════════════════════════════

print_step("Admin kullanıcısı oluşturuluyor...")

if db.users.find_one({"email": ADMIN_EMAIL}):
    print_skip(f"Admin: {ADMIN_EMAIL}")
else:
    # Şifre güç kontrolü
    pw = ADMIN_PASSWORD
    errors = []
    if len(pw) < 8:          errors.append("En az 8 karakter")
    if not any(c.isupper() for c in pw): errors.append("Büyük harf gerekli")
    if not any(c.isdigit() for c in pw): errors.append("Rakam gerekli")
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in pw): errors.append("Özel karakter gerekli")

    if errors:
        print(f"\n  ❌ ZAYIF ŞİFRE: {', '.join(errors)}")
        print("  Admin oluşturulamadı. Scripti tekrar çalıştırıp güçlü şifre girin.")
        sys.exit(1)

    db.users.insert_one({
        "user_id":    generate_user_id(),
        "email":      ADMIN_EMAIL,
        "password":   hash_pw(ADMIN_PASSWORD),
        "name":       "ANTICCA Admin",
        "role":       "admin",
        "created_at": now(),
    })
    print_ok(f"Admin oluşturuldu: {ADMIN_EMAIL}")
    print("  ⚠️  Şifreyi güvenli bir yerde saklayın!")


# ══════════════════════════════════════════════════════════════════
# 5. ÖZET RAPOR
# ══════════════════════════════════════════════════════════════════

print_step("Kurulum tamamlandı! Özet:")

counts = {}
for col in COLLECTIONS.keys():
    counts[col] = db[col].count_documents({})

print(f"""
  ┌─────────────────────────────────────────┐
  │  VERİTABANI: {DB_NAME:<27} │
  ├─────────────────────────────────────────┤
  │  Koleksiyon         │  Döküman Sayısı   │
  ├─────────────────────────────────────────┤""")

for col, count in counts.items():
    print(f"  │  {col:<20} │  {count:<18} │")

print(f"""  └─────────────────────────────────────────┘

  ✅ Tüm koleksiyonlar hazır
  ✅ Tüm index'ler kuruldu
  ✅ JSON Schema validasyonları aktif
  ✅ Başlangıç verileri yüklendi
  ✅ Admin kullanıcısı: {ADMIN_EMAIL}

  📋 Sonraki adım:
     Backend'inizin .env dosyasına ekleyin:
     MONGO_URL={MONGO_URL}
     DB_NAME={DB_NAME}
""")

client.close()

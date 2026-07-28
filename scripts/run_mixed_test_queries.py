# app2/scripts/run_mixed_test_queries.py
import os
import sys
import time
import uuid

# ======================
# FIX PATH (مهم‌ترین قسمت)
# ======================
# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ======================
# Imports
# ======================
from app2.main import app  # حالا درست کار می‌کند
from fastapi.testclient import TestClient

test_client = TestClient(app)

# =====================================================
# دیتاست ترکیبی تست
# =====================================================
MIXED_QUERIES = [
    # ── GOOD QUERIES (باید قبول شود) ──
    "تبریک روز مادر برای اینستاگرام",
    "استوری تولد کودکانه",
    "ویدیو تبریک عقد و عروسی",
    "قالب استوری ولنتاین",
    "کلیپ تبریک سالگرد ازدواج",
    "تبریک نوروز برای اینستاگرام",
    "استوری روز پدر",
    "قالب تبریک کریسمس",
   "برای تولد دوستم استوری تبریک میخوام",
    "روز مادر کلیپ خوب چی داری؟",
    "یک لوگوموشن خفن برای معرفی برندم میخوام",
    "لوگوموشن برای استوری ایسنتاگرام چیزی داری",

    # ── BAD / CHAT-LIKE (باید بلاک شود) ──
    #"سلام چطوری؟",
   # "خیلی خری میدونستی؟",
   # "امروز چیکار کنم؟",
   # "فکر میکنی من خوبم؟",
   # "حالت چطوره؟",
   # "بگو ببینم چی خبر؟",
   # "اصلا تو چیزی از تبریک تولد میدونی؟",
   # "میخوام روز مادر رو به مامانم تبریک بگم چی براش بفرستم"

    # ── EDGE CASES ──
   # "تولد",                              # خیلی کوتاه
   # "تبریک روز مادر برای اینستاگرام استوری و پست و ریلز و ویدیو",  # خیلی طولانی
   # "همه قالب‌های تولد",                 # Broad query
  #  "دانلود فیلم تولد",                   # ممکن است بلاک شود
   # "تبریک تولد کودک",                   # خوب
  #  "!!!!!!؟؟؟؟؟😂😂😂",                   # spam
  #  "cfdsvgzdfv fbhgfhft",                # gibberish
]

def run_mixed_test():
    print("🚀 شروع تست ترکیبی کویری‌ها...\n")
    total = len(MIXED_QUERIES)
    success = 0
    blocked = 0

    for i, query in enumerate(MIXED_QUERIES, 1):
        request_id = str(uuid.uuid4())
        print(f"[{i:2d}/{total}] Query: {query}")

        try:
            response = test_client.post(
                "/api/v1/search",
                json={"query": query},
                headers={"X-Request-ID": request_id}
            )

            data = response.json()
            mode = data.get("mode", "unknown")
            reason = data.get("reason", "")

            if mode in ["blocked_by_firewall", "validation_error", "invalid_query"]:
                print(f"   → BLOCKED | {reason}")
                blocked += 1
            else:
                result_count = len(data.get("results", []))
                print(f"   → SUCCESS | {result_count} results")
                success += 1

        except Exception as e:
            print(f"   → ERROR   | {e}")

        time.sleep(0.3)

    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    print(f"Total Queries     : {total}")
    print(f"Successful        : {success}")
    print(f"Blocked           : {blocked}")
    print(f"Success Rate      : {success/total*100:.1f}%")
    print(f"Blocked Rate      : {blocked/total*100:.1f}%")
    print("="*70)
    print("✅ تست تمام شد. حالا جدول retrieval_logs را چک کن.")

if __name__ == "__main__":
    run_mixed_test()

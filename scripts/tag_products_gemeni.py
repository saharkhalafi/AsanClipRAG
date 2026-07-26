import asyncio
import hashlib
import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple
from weakref import WeakKeyDictionary

import pandas as pd
from app.core.config import GEMINI_API_KEY
from app.services.cache_service import get_cache, set_cache
from dotenv import load_dotenv
from google import genai
from google.genai import types
from sqlalchemy import create_engine, text

load_dotenv()

# ========================= LOGGING =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("tagger.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ========================= CONFIG =========================
DB_URI = os.getenv("DATABASE_URL")

if not DB_URI:
    raise ValueError("Missing DATABASE_URL")
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY")

TABLE              = "asanclipproducts"
TAG_VERSION        = 3          # bump when labels/keywords change → auto re-tags stale rows
BATCH_SIZE         = 50
MAX_RETRIES        = 3
GEMINI_CONCURRENCY = 5          # safe under free-tier 10 RPM; raise on paid tier

engine = create_engine(DB_URI, pool_pre_ping=True)
client = genai.Client(api_key=GEMINI_API_KEY)

# ========================= LABELS =========================
# ORDER MATTERS inside each dict — more specific entries before generic ones.
# match_label() returns the FIRST keyword match, so "قالب استوری" must appear
# before "قالب اینستاگرام", and "ویدیو" (generic fallback) must be last.
#
# NO trailing/leading spaces in keys — they silently break ALLOWED validation.

PRODUCT_TYPES: Dict[str, List[str]] = {
    "لوگو موشن":       ["لوگو موشن", "لوگوموشن", "logo motion", "logo reveal"],
    "قالب استوری":     ["قالب استوری", "استوری اینستاگرام", "instagram story"],
    "قالب پست":        ["قالب پست", "پست اینستاگرام", "instagram post", "social post"],
    "قالب تبریک":      ["قالب تبریک", "کارت تبریک", "greeting card"],
    "انیمیشن":         ["انیمیشن", "animation", "موشن گرافیک", "motion graphic"],
    "قالب معرفی":      ["قالب معرفی", "معرفی محصول", "intro template", "opener"],
    "اسلایدشو":        ["اسلایدشو", "slideshow", "slide show"],
    "افتتاحیه":        ["افتتاحیه", "opening ceremony"],
    "پروموشن":         ["پروموشن", "تیزر تبلیغاتی", "promo video"],
    "آموزشی":          ["قالب آموزشی", "ویدیو آموزشی", "educational video"],
    "خبری":            ["قالب خبری", "برنامه خبری", "news template"],
    "سرگرمی":          ["قالب سرگرمی", "entertainment template"],
    "ورزشی":           ["قالب ورزشی", "sports template"],
    "مذهبی":           ["قالب مذهبی", "قالب اسلامی", "islamic template"],
    "قالب اینستاگرام": ["قالب اینستاگرام", "instagram template"],
    "ویدیو":           ["ویدیو", "video", "کلیپ", "تیزر"],   # generic — keep last
}

OCCASIONS: Dict[str, List[str]] = {
    "تولد":          ["تولد", "جشن تولد", "birthday"],
    "عروسی":         ["عروسی", "مراسم عروسی", "wedding"],
    "روز مادر":      ["روز مادر", "mothers day"],
    "روز پدر":       ["روز پدر", "fathers day"],
    "نوروز":         ["نوروز", "عید نوروز", "nowruz"],
    "یلدا":          ["شب یلدا", "شب چله", "yalda night"],
    "ماه رمضان":     ["ماه رمضان", "ماه مبارک رمضان", "ramadan"],
    "محرم":          ["محرم", "عاشورا", "ashura"],
    "هالووین":       ["هالووین", "halloween"],
    "فوتبال":        ["جام جهانی", "لیگ قهرمانان", "world cup", "champions league"],
    "سال نو میلادی": ["سال نو میلادی", "کریسمس", "christmas", "new year"],
    "عید فطر":       ["عید فطر", "عید قربان", "eid al-fitr"],
}

PLATFORMS: Dict[str, List[str]] = {
    "اینستاگرام": ["اینستاگرام", "instagram"],
    "یوتیوب":     ["یوتیوب", "youtube"],
    "تلگرام":     ["تلگرام", "telegram"],
    "تیک تاک":    ["تیک تاک", "تیکتاک", "tiktok"],
    "لینکدین":    ["لینکدین", "linkedin"],
}
# NOTE: removed short ambiguous aliases ("ig", "yt", "insta", "story", "reels")
# that caused false positives. If text says "اینستاگرام" the full word is enough.

ALLOWED: Dict[str, set] = {
    "product_type": {k.strip() for k in PRODUCT_TYPES},
    "occasion":     {k.strip() for k in OCCASIONS},
    "platform":     {k.strip() for k in PLATFORMS},
}

# ========================= OCCASION SIGNAL VOCABULARY =========================
# Used to decide whether it's even worth calling Gemini for occasion.
# These are broad vocabulary hints — NOT the label keywords themselves.
# If NONE of these appear in the text, the template has no occasion → skip Gemini.
_OCCASION_VOCAB = {
    _kw for kws in OCCASIONS.values() for _kw in kws
} | {
    "مناسبت", "جشن", "جشنواره", "مراسم", "سالگرد", "تعطیل",
    "occasion", "celebration", "festival", "anniversary", "holiday",
}

# ========================= NORMALIZE + PRE-BUILD KEYWORD TABLES =========================
def _normalize(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^\w\s\u0600-\u06FF]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _prenormalize(rules: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Normalize all keywords once at startup — no per-row cost."""
    return {label: [_normalize(kw) for kw in kws] for label, kws in rules.items()}

_PT_NORM  = _prenormalize(PRODUCT_TYPES)
_OC_NORM  = _prenormalize(OCCASIONS)
_PL_NORM  = _prenormalize(PLATFORMS)
_OC_VOCAB = {_normalize(w) for w in _OCCASION_VOCAB}

def hash_text(t: str) -> str:
    return hashlib.md5(_normalize(t).encode()).hexdigest()

# ========================= RULE ENGINE =========================
def match_label(text: str, norm_rules: Dict[str, List[str]]) -> Optional[str]:
    """
    Word-boundary match against pre-normalized keyword lists.
    Word boundaries (\b) prevent short keywords from matching inside longer words.
    Text must already be normalized before calling.
    """
    for label, kws in norm_rules.items():
        for kw in kws:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                return label
    return None

def rules_extract(text: str) -> dict:
    """Pure rule-based extraction — zero cost, always runs."""
    t = _normalize(text)
    return {
        "product_type": match_label(t, _PT_NORM),
        "occasion":     match_label(t, _OC_NORM),
        "platform":     match_label(t, _PL_NORM),
    }

def has_occasion_signals(text: str) -> bool:
    """
    Returns True if the text contains vocabulary suggesting an occasion exists
    but wasn't caught by the rule engine (worth asking Gemini).
    Returns False for generic/brand templates with no event vocabulary at all.
    """
    t = _normalize(text)
    return any(re.search(rf"\b{re.escape(w)}\b", t) for w in _OC_VOCAB)

# ========================= CACHE =========================
_CV = "cache_v"

def _is_fresh(cached: Optional[dict]) -> bool:
    """Cache entry is valid only if written by the current TAG_VERSION."""
    return isinstance(cached, dict) and cached.get(_CV) == TAG_VERSION

# ========================= ASYNC GEMINI =========================


_semaphores = WeakKeyDictionary()

def _get_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()

    sem = _semaphores.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(GEMINI_CONCURRENCY)
        _semaphores[loop] = sem

    return sem

async def _gemini_call_async(text: str, key: str, need_pt: bool, need_oc: bool) -> dict:
    """
    Single async Gemini call.
    need_pt / need_oc: tells the prompt which fields are actually needed,
    so Gemini doesn't guess at fields the rule engine already resolved.

    Platform is INTENTIONALLY excluded from Gemini — rule engine handles it
    with full-word matching, and Gemini hallucinates platform too aggressively.
    """
    async with _get_semaphore():

        fields_needed = []
        if need_pt:
            fields_needed.append("product_type")
        if need_oc:
            fields_needed.append("occasion")

        prompt = f"""You are a strict metadata extractor for Persian/English video templates.
Return ONLY valid JSON — no markdown, no preamble:

{{
  "product_type": string|null,
  "occasion": string|null
}}

STRICT RULES:
- Only fill fields listed in FIELDS NEEDED below. Return null for others.
- Use EXACTLY the label strings from the allowed lists, or null.
- DO NOT infer. DO NOT guess. If not clearly stated → null.
- occasion: null unless a specific event/holiday is explicitly named in the text.

FIELDS NEEDED: {fields_needed}

product_type options: {list(PRODUCT_TYPES.keys())}
occasion options:     {list(OCCASIONS.keys())}

TEXT:
{text[:1200]}
"""
        for attempt in range(MAX_RETRIES):
            try:
                loop = asyncio.get_event_loop()
                res  = await loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0,
                            response_mime_type="application/json",
                        ),
                    )
                )
                data = json.loads(res.text or "{}")

                result: dict = {
                    "product_type": data.get("product_type") if need_pt else None,
                    "occasion":     data.get("occasion")     if need_oc else None,
                    "platform":     None,   # never from Gemini
                    _CV:            TAG_VERSION,
                }

                # Validate + strip whitespace — prevent hallucinated values
                for field in ("product_type", "occasion"):
                    raw = result[field]
                    val = raw.strip() if isinstance(raw, str) else raw
                    if val is not None and val not in ALLOWED[field]:
                        log.warning(f"Gemini invalid {field}='{raw}' → None")
                        val = None
                    result[field] = val

                log.info(f"Gemini → pt={result['product_type']} oc={result['occasion']}")
                set_cache(key, result)
                return result

            except Exception as e:
                if "429" in str(e):
                    wait = (2 ** attempt) + 1
                    log.warning(f"Rate limited — waiting {wait}s (attempt {attempt+1})")
                    await asyncio.sleep(wait)
                else:
                    log.warning(f"Gemini error attempt={attempt+1}: {e}")
                    await asyncio.sleep(1)

        fallback = {"product_type": None, "occasion": None, "platform": None, _CV: TAG_VERSION}
        set_cache(key, fallback)
        return fallback

async def _return_value(value: dict) -> dict:
    return value

async def _safe_call(coro) -> dict:  # type: ignore[type-arg]
    try:
        return await coro
    except Exception as e:
        log.warning(f"Coroutine failed: {e}")
        return {"product_type": None, "occasion": None, "platform": None}

async def gemini_batch_async(
    calls: List[Tuple[int, str, bool, bool]]   # (row_idx, text, need_pt, need_oc)
) -> Dict[int, dict]:
    """
    Fire all needed Gemini calls concurrently up to GEMINI_CONCURRENCY at a time.
    Cached results are returned immediately without hitting the API.
    """
    task_indices: List[int] = []
    coroutines:   List      = []

    for idx, product_text, need_pt, need_oc in calls:
        key    = hash_text(product_text)
        cached = get_cache(key)
        if isinstance(cached, dict) and _is_fresh(cached):
             coroutines.append(_return_value(cached))
        else:
             coroutines.append(_gemini_call_async(product_text, key, need_pt, need_oc))
        task_indices.append(idx)

    results: List[dict] = await asyncio.gather(*coroutines)
    return dict(zip(task_indices, results))

# ========================= HYBRID EXTRACT (BATCH) =========================
def extract_batch(rows: List[dict]) -> List[Tuple[dict, str]]:
    """
    Decision tree per row
    ─────────────────────
    1. Run rule engine (word-boundary keywords) on all rows — free
    2. For each row decide whether Gemini is needed:
         • need_pt = product_type still missing
         • need_oc = occasion missing AND text has occasion vocabulary
         • platform = NEVER sent to Gemini (hallucination risk too high)
    3. Fire all Gemini calls concurrently
    4. Merge: rule engine results take priority, Gemini fills gaps only
    """
    normalized = [_normalize(build_input_text(r)) for r in rows]
    rule_res   = [rules_extract(t) for t in normalized]

    # Decide which rows need Gemini and for which fields
    gemini_calls: List[Tuple[int, str, bool, bool]] = []

    for i, (res, t) in enumerate(zip(rule_res, normalized)):
        need_pt = res["product_type"] is None
        need_oc = res["occasion"] is None and has_occasion_signals(t)

        if not need_pt and not need_oc:
            continue  # rules resolved everything worth resolving → skip Gemini

        key    = hash_text(t)
        cached = get_cache(key)
        if _is_fresh(cached):
            continue  # fresh cache covers this row → no API call needed

        gemini_calls.append((i, t, need_pt, need_oc))

    total_gemini = len(gemini_calls)
    total_cached = sum(
        1 for _, t, _, _ in gemini_calls
        if _is_fresh(get_cache(hash_text(t)))
    )
    log.info(
        f"  Rules resolved: {len(rows) - total_gemini}/{len(rows)} | "
        f"Gemini calls: {total_gemini} | "
        f"Cache hits: {total_cached}"
    )

    # Fire concurrent Gemini calls
    gem_results: Dict[int, dict] = {}
    if gemini_calls:
        gem_results = asyncio.run(gemini_batch_async(gemini_calls))

    # Merge and build final output
    final: List[Tuple[dict, str]] = []

    for i, (res, t) in enumerate(zip(rule_res, normalized)):
        gem = gem_results.get(i)

        # Also try fresh cache for rows that had cached results
        if not isinstance(gem, dict):
            cached = get_cache(hash_text(t))
            gem    = cached if _is_fresh(cached) else {}

        # Merge — rule engine always wins, Gemini fills only what's missing
        pt = res["product_type"] or (gem.get("product_type") if gem else None)
        oc = res["occasion"]     or (gem.get("occasion")     if gem else None)
        pl = res["platform"]     # platform: rules only, never from Gemini

        # Determine source for observability
        used_rules  = bool(res["product_type"] or res["occasion"] or res["platform"])
        used_gemini = i in gem_results
        used_cache  = not used_gemini and _is_fresh(get_cache(hash_text(t)))

        if used_gemini and used_rules:
            source = "rules+gemini"
        elif used_gemini:
            source = "gemini"
        elif used_cache:
            source = "cached"
        else:
            source = "rules"

        final.append((
            {
                "product_type": pt or "ویدیو",
                "occasion":     oc,
                "platform":     pl,
            },
            source,
        ))

    return final

# ========================= INPUT TEXT =========================
def build_input_text(row: dict) -> str:
    parts = [
        str(row.get("name") or "").strip(),
        str(row.get("short_description") or "").strip(),
        str(row.get("description") or "").strip(),
    ]
    return " | ".join(p for p in parts if p)

# ========================= RAG TEXT =========================
def build_rag_text(tags: dict, raw_text: str) -> str:
    """
    Format for hybrid RAG:
      "نوع: X | مناسبت: Y | پلتفرم: Z | <raw text>"

    Labelled prefix lets the semantic model map user queries like
    "قالب تولد اینستاگرام" to the right metadata fields.
    Raw text follows for full semantic coverage.
    """
    pt = tags.get("product_type") or ""
    oc = tags.get("occasion") or ""
    pl = tags.get("platform") or ""

    labels = " | ".join(filter(None, [
        f"نوع: {pt}" if pt else None,
        f"مناسبت: {oc}" if oc else None,
        f"پلتفرم: {pl}" if pl else None,
    ]))

    return " | ".join(p for p in [labels, raw_text] if p)

# ========================= DB SCHEMA =========================
with engine.begin() as conn:
    # Add columns if missing
    conn.execute(text(f"""
        ALTER TABLE {TABLE}
        ADD COLUMN IF NOT EXISTS product_type TEXT,
        ADD COLUMN IF NOT EXISTS occasion     TEXT,
        ADD COLUMN IF NOT EXISTS platform     TEXT,
        ADD COLUMN IF NOT EXISTS rag_text     TEXT,
        ADD COLUMN IF NOT EXISTS tag_status   TEXT    DEFAULT 'pending',
        ADD COLUMN IF NOT EXISTS tag_version  INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS tag_source   TEXT
    """))
    # FIX: backfill NULLs on rows that existed before the columns were added.
    # ALTER TABLE only sets DEFAULT for future inserts — existing rows get NULL.
    # NULL IN ('pending','failed') = FALSE and NULL < n = NULL (also FALSE),
    # so rows with NULL tag_status/tag_version are silently skipped every run.
    conn.execute(text(f"""
        UPDATE {TABLE}
        SET tag_status  = 'pending',
            tag_version = 0
        WHERE tag_status IS NULL
           OR tag_version IS NULL
    """))
log.info("✅ DB schema ready")

# ========================= LOAD =========================
log.info("Loading rows...")
df = pd.read_sql(f"""
    SELECT id, name, short_description, description
    FROM {TABLE}
    WHERE tag_status IS NULL                              -- pre-migration rows (safety net)
       OR tag_version IS NULL                            -- pre-migration rows (safety net)
       OR tag_status IN ('pending', 'failed')            -- normal unprocessed / errored
       OR (tag_status = 'done' AND tag_version < {TAG_VERSION})  -- stale — labels changed
    ORDER BY id
""", engine)
total = len(df)
log.info(f"Rows to process: {total}")

# ========================= PROCESS IN BATCHES =========================
processed  = 0
failed_ids: List[int] = []

for batch_start in range(0, total, BATCH_SIZE):
    batch_df   = df.iloc[batch_start : batch_start + BATCH_SIZE]
    batch_rows = batch_df.to_dict("records")
    batch_num  = batch_start // BATCH_SIZE + 1

    log.info(f"\nBatch {batch_num} | rows {batch_start}–{batch_start + len(batch_rows) - 1}")

    input_texts = [build_input_text(r) for r in batch_rows]

    try:
        tag_results = extract_batch(batch_rows)
    except Exception as e:
        log.error(f"Batch {batch_num} failed entirely: {e}")
        failed_ids.extend([r["id"] for r in batch_rows])
        continue

    updates_ok:   List[dict] = []
    updates_fail: List[dict] = []

    for row, input_text, (tags, source) in zip(batch_rows, input_texts, tag_results):
        try:
            rag = build_rag_text(tags, input_text)
            updates_ok.append({
                "id":          row["id"],
                "pt":          tags["product_type"],
                "oc":          tags["occasion"],
                "pl":          tags["platform"],
                "rag":         rag,
                "tag_version": TAG_VERSION,
                "tag_source":  source,
            })
            log.info(f"  id={row['id']} [{source}] → {tags}")
        except Exception as e:
            log.error(f"  id={row['id']} FAILED: {e}")
            updates_fail.append({"id": row["id"]})
            failed_ids.append(row["id"])

    if updates_ok:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"""
                    UPDATE {TABLE}
                    SET product_type = :pt,
                        occasion     = :oc,
                        platform     = :pl,
                        rag_text     = :rag,
                        tag_status   = 'done',
                        tag_version  = :tag_version,
                        tag_source   = :tag_source
                    WHERE id = :id
                """), updates_ok)
            processed += len(updates_ok)
            log.info(
                f"  ✅ Saved {len(updates_ok)} | "
                f"progress {processed}/{total} ({processed / total * 100:.1f}%)"
            )
        except Exception as e:
            log.error(f"  ❌ DB write failed: {e}")
            failed_ids.extend([u["id"] for u in updates_ok])

    if updates_fail:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(f"UPDATE {TABLE} SET tag_status = 'failed' WHERE id = :id"),
                    updates_fail,
                )
        except Exception as e:
            log.error(f"  ❌ Could not mark failures: {e}")

# ========================= SUMMARY =========================
log.info(f"\n{'='*50}")
log.info(f"🎉 DONE — {processed}/{total} tagged successfully")
if failed_ids:
    log.warning(f"⚠️  Failed IDs: {failed_ids} — re-run to retry")
log.info(f"{'='*50}")

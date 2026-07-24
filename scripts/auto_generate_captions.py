# scripts/auto_generate_captions.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from app2.services.caption_service import CaptionService
from app2.db.session import get_db   # session factory خودت


def detect_occasion(text2: str) -> tuple:
    """تشخیص هوشمند دسته‌بندی مناسبت"""
    if not text2:
        return None, None
    t = text2.lower()
    
    if any(k in t for k in ["تولد", "birthday", "سال تولد", "birth day"]):
        return "تولد", "occasion"
    elif any(k in t for k in ["سالگرد", "anniversary", "سالگرد ازدواج"]):
        return "سالگرد_ازدواج", "occasion"
    elif any(k in t for k in ["عقد", "عروسی", "wedding", "marriage", "عروس", "عروسی"]):
        return "عقد_عروسی", "occasion"
    elif any(k in t for k in ["ولنتاین", "valentine", "روز عشق", "valentine's"]):
        return "ولنتاین", "occasion"
    elif any(k in t for k in ["نوروز", "سال نو", "عیدنوروز", "nowruz"]):
        return "نوروز", "occasion"
    elif "کریسمس" in t or "christmas" in t:
        return "کریسمس", "occasion"
    elif any(k in t for k in ["یلدا", "شب یلدا", "yaldā"]):
        return "یلدا", "occasion"
    elif any(k in t for k in ["روز پدر"]):
        return "روز پدر", "occasion"
    elif any(k in t for k in ["روز مادر","روز زن"]):
        return "روز مادر", "occasion"
    elif any(k in t for k in ["روز معلم"]):
        return "روز معلم", "occasion" 
    elif any(k in t for k in ["روز مهندس"]):
        return "روز مهندس", "occasion" 
    elif any(k in t for k in ["پیام تسلیت", "تسلیت"]):
        return "پیام تسلیت", "occasion"   
    elif any(k in t for k in ["تخفیف", "حراج","فروش ویژه", "off", "sale"]):
        return "تخفیف", "occasion"
    elif any(k in t for k in ["بلک فرایدی", "black friday", "جمعه سیاه"]):
        return "بلک فرایدی", "occasion"
    elif any(k in t for k in ["محصول جدید", "new product"]):
        return "محصول جدید", "occasion"
    elif any(k in t for k in ["افتتاحیه"]):
        return "افتتاحیه", "occasion"
    elif any(k in t for k in ["دعوت"]):
        return "دعوت", "occasion"
    return None, None


def auto_generate_captions(db: Session, limit: int = 10000):
    service = CaptionService(db)
    
    print("🔄 شروع تشخیص و تولید کپشن...")

    # استفاده صحیح از text()
    query = text("""
        SELECT id, occasion, name, product_type, short_description 
        FROM asanclipproducts 
        WHERE occasion IS NOT NULL 
           OR name IS NOT NULL 
        LIMIT :limit
    """)

    products = db.execute(query, {"limit": limit}).fetchall()

    total = 0
    for p in products:
        product_id = p.id
        text2 = f"{p.occasion or ''} {p.name or ''} {p.product_type or ''} {p.short_description or ''}"
        
        category, _ = detect_occasion(text2)
        
        if category:
            if category == "تولد":
                service.add_caption(product_id, "تولدت مبارک عزیزم 🎂✨ امسال پر از اتفاق‌های قشنگ برات باشه", "occasion", category, 1)
                service.add_caption(product_id, "تولد تو مبارک 🌟 امیدوارم همیشه لبخندت پررنگ باشه", "occasion", category, 2)
                service.add_caption(product_id, "امروز روز توئه! 🎉 خوش بگذرون و حسابی بدرخش", "occasion", category, 3)
                service.add_caption(product_id, "یک سال بزرگ‌تر، یک دنیا قشنگ‌تر ✨ تولدت مبارک", "occasion", category, 4)
                service.add_caption(product_id, "کیک، لبخند، شادی… بهترین ترکیب دنیا 🎂🥳", "occasion", category, 5)
                service.add_caption(product_id, "امیدوارم امسال بهترین نسخه‌ی زندگی‌تو تجربه کنی 🌈", "occasion", category, 6)
                service.add_caption(product_id, "تولدت فقط یه روز نیست، شروع یه سال جدیده 💛", "occasion", category, 7)
                service.add_caption(product_id, "امروز باید فقط بخندی و خوشحال باشی 🎈 تولدت مبارک", "occasion", category, 8)
                service.add_caption(product_id, "یه دنیا آرزو برای یه آدم خاص 🌟 تولدت مبارک", "occasion", category, 9)
                service.add_caption(product_id, "بیشتر از همیشه بدرخش ✨ این سال مال توئه", "occasion", category, 10)
                service.add_caption(product_id, "تولدت مبارک رفیق 🎉 خوشحال باش چون لیاقتشو داری", "occasion", category, 11)
                service.add_caption(product_id, "زندگی قشنگ‌تر میشه وقتی تو توش هستی 🎂💖", "occasion", category, 12)
                service.add_caption(product_id, "امروز فقط جشنه! 🎊 تولدت مبارک", "occasion", category, 13)
                service.add_caption(product_id, "یک سال دیگه از قشنگی‌های تو گذشت 🌟", "occasion", category, 14)
                service.add_caption(product_id, "همه چیز امروز باید شیرین باشه مثل کیک تولدت 🎂", "occasion", category, 15)
                service.add_caption(product_id, "بهترین‌ها هنوز در راهن ✨ تولدت مبارک", "occasion", category, 16)
                service.add_caption(product_id, "امروز دنیا به احترام تو لبخند می‌زنه 😊", "occasion", category, 17)
                service.add_caption(product_id, "تولدت مبارک! یه سال جدید، یه شروع تازه 🚀", "occasion", category, 18)
                service.add_caption(product_id, "آرزو می‌کنم همه آرزوهات واقعی بشن 💫", "occasion", category, 19)
                service.add_caption(product_id, "تو خاصی، امروز خاص‌تر شدی 🎂✨", "occasion", category, 20)
                total += 20

            elif category == "سالگرد_ازدواج":
                service.add_caption(product_id, "سالگرد عشق‌تون مبارک ❤️ هنوزم مثل روز اول زیباست", "occasion", category, 1)
                service.add_caption(product_id, "عشق واقعی یعنی هر سال دوباره انتخاب کردن همدیگه 💍", "occasion", category, 2)
                service.add_caption(product_id, "کنار هم بودن، قشنگ‌ترین اتفاق زندگیه ✨", "occasion", category, 3)
                service.add_caption(product_id, "سال‌ها گذشت اما عشق‌تون عمیق‌تر شد ❤️", "occasion", category, 4)
                service.add_caption(product_id, "سالگردتون مبارک 🌹 یه عشق موندگار و واقعی", "occasion", category, 5)
                service.add_caption(product_id, "سالگرد ازدواج شما مبارک 💖", "occasion", category, 6)
                service.add_caption(product_id, "با هم بودن یعنی خوشبختی واقعی ✨", "occasion", category, 7)
                service.add_caption(product_id, "هر سال یه فصل جدید از عشق 📖❤️", "occasion", category, 8)
                service.add_caption(product_id, "عشق‌تون همیشه بدرخشه 💫 سالگرد مبارک", "occasion", category, 9)
                service.add_caption(product_id, "زندگی وقتی قشنگه که دو نفر همدل باشن 💍", "occasion", category, 10)
                service.add_caption(product_id, "این عشق ارزش جشن گرفتن داره 🎉", "occasion", category, 11)
                service.add_caption(product_id, "کنار هم یعنی کامل‌تر شدن ❤️", "occasion", category, 12)
                service.add_caption(product_id, "سالگرد عشق، سالگرد زندگی 🌹", "occasion", category, 13)
                service.add_caption(product_id, "با هم قوی‌تر، با هم عاشق‌تر ✨", "occasion", category, 14)
                service.add_caption(product_id, "عشق شما داستانی بی‌پایانه 💖", "occasion", category, 15)
                service.add_caption(product_id, "سالگردتون مبارک 🌟 همیشه خوشبخت بمونید", "occasion", category, 16)
                service.add_caption(product_id, "هر روز با هم بودن یه هدیه‌ست 🎁❤️", "occasion", category, 17)
                service.add_caption(product_id, "عشق واقعی هر سال قشنگ‌تر میشه 💍", "occasion", category, 18)
                service.add_caption(product_id, "شما دلیل قشنگ بودن عشق هستید ✨", "occasion", category, 19)
                service.add_caption(product_id, "به عشق‌تون افتخار کنید ❤️ سالگرد مبارک", "occasion", category, 20)
                total += 20

            elif category == "عقد_عروسی":
                service.add_caption(product_id, "آغاز یک زندگی قشنگ 💍 مبارک باشه", "occasion", category, 1)
                service.add_caption(product_id, "از امروز دو تا قلب، یک مسیر ❤️", "occasion", category, 2)
                service.add_caption(product_id, "به شروع عشق جدیدتون خوش آمدید ✨", "occasion", category, 3)
                service.add_caption(product_id, "امروز قصه‌ی شما شروع شد 📖💍", "occasion", category, 4)
                service.add_caption(product_id, "عقدتون مبارک 🌹 پر از عشق باشید", "occasion", category, 5)
                service.add_caption(product_id, "مبارک باشه عروس و داماد' 💖", "occasion", category, 6)
                service.add_caption(product_id, "شروع یه عمر خوشبختی ✨", "occasion", category, 7)
                service.add_caption(product_id, "با هم برای همیشه ❤️💍", "occasion", category, 8)
                service.add_caption(product_id, "زیباترین بله‌ی دنیا امروز گفته شد 💫", "occasion", category, 9)
                service.add_caption(product_id, "عشق یعنی این لحظه ✨", "occasion", category, 10)
                service.add_caption(product_id, "شروع زندگی مشترک مبارک 🎉", "occasion", category, 11)
                service.add_caption(product_id, "از امروز شما یکی شدید ❤️", "occasion", category, 12)
                service.add_caption(product_id, "لحظه‌ای که همیشه موندگاره 💍", "occasion", category, 13)
                service.add_caption(product_id, "خوشبختی از اینجا شروع شد ✨", "occasion", category, 14)
                service.add_caption(product_id, "عشق واقعی امروز رسمی شد ❤️", "occasion", category, 15)
                service.add_caption(product_id, "بهترین شروع برای یک عمر 🌹", "occasion", category, 16)
                service.add_caption(product_id, "کنار هم یعنی همه چیز 💍", "occasion", category, 17)
                service.add_caption(product_id, "لحظه‌های ناب زندگی ✨", "occasion", category, 18)
                service.add_caption(product_id, "امروز فقط عشق جریان داره ❤️", "occasion", category, 19)
                service.add_caption(product_id, "شروع یک قصه‌ی بی‌انتها 📖💍", "occasion", category, 20)
                total += 20

            elif category == "ولنتاین":
                service.add_caption(product_id, "ولنتاین مبارک عشق من ❤️", "occasion", category, 1)
                service.add_caption(product_id, "عشق یعنی تو 💘", "occasion", category, 2)
                service.add_caption(product_id, "امروز فقط عشق مهمه 🌹", "occasion", category, 3)
                service.add_caption(product_id, "تو دلیل لبخند منی 😊❤️", "occasion", category, 4)
                service.add_caption(product_id, "ولنتاین یعنی یاد تو 💖", "occasion", category, 5)
                service.add_caption(product_id, f"ولنتاین مبارک {p.name or 'عشق من'} 💘", "occasion", category, 6)
                service.add_caption(product_id, "قشنگ‌ترین حس دنیا عشق توئه ✨", "occasion", category, 7)
                service.add_caption(product_id, "هر روز با تو ولنتاینه ❤️", "occasion", category, 8)
                service.add_caption(product_id, "تو خودِ عشق هستی 💖", "occasion", category, 9)
                service.add_caption(product_id, "بدون تو هیچ روزی قشنگ نیست 🌹", "occasion", category, 10)
                service.add_caption(product_id, "عشق یعنی همین لحظه 💘", "occasion", category, 11)
                service.add_caption(product_id, "تو خاص‌ترین هدیه‌ی زندگی منی 🎁❤️", "occasion", category, 12)
                service.add_caption(product_id, "ولنتاین فقط یه بهونه‌ست برای گفتن دوستت دارم 💖", "occasion", category, 13)
                service.add_caption(product_id, "با تو همه چیز قشنگ‌تره ✨", "occasion", category, 14)
                service.add_caption(product_id, "عشق من، ولنتاینت مبارک 🌹", "occasion", category, 15)
                service.add_caption(product_id, "تو دلیل عاشق بودنمی 💘", "occasion", category, 16)
                service.add_caption(product_id, "قلبم مال توئه ❤️", "occasion", category, 17)
                service.add_caption(product_id, "با تو دنیا بهتره ✨💖", "occasion", category, 18)
                service.add_caption(product_id, "عشق واقعی تویی 💘", "occasion", category, 19)
                service.add_caption(product_id, "همیشه دوستت دارم ❤️", "occasion", category, 20)
                total += 20

            elif category == "نوروز":
                service.add_caption(product_id, "نوروز مبارک 🌸 سالی پر از شادی برات آرزو می‌کنم", "occasion", category, 1)
                service.add_caption(product_id, "بهار اومده 🌿 وقت شروع دوباره‌ست", "occasion", category, 2)
                service.add_caption(product_id, "نوروز یعنی امید تازه ✨", "occasion", category, 3)
                service.add_caption(product_id, "سال نو، حال نو 🌸", "occasion", category, 4)
                service.add_caption(product_id, "بهترین‌ها در راهن 🌿 نوروز مبارک", "occasion", category, 5)
                service.add_caption(product_id, f"نوروز مبارک {p.name or 'دوست من'} 🌸", "occasion", category, 6)
                service.add_caption(product_id, "بهار یعنی شروع دوباره ✨", "occasion", category, 7)
                service.add_caption(product_id, "پر از اتفاق‌های قشنگ باشی 🌿", "occasion", category, 8)
                service.add_caption(product_id, "نوروز، جشن زندگی 🌸", "occasion", category, 9)
                service.add_caption(product_id, "سالی پر از لبخند برات 🌿", "occasion", category, 10)
                service.add_caption(product_id, "بهار رسید یعنی امید برگشت ✨", "occasion", category, 11)
                service.add_caption(product_id, "سال نو مبارک 🌸 بهترین‌ها برات", "occasion", category, 12)
                service.add_caption(product_id, "دوباره شروع کن 🌿 نوروز مبارک", "occasion", category, 13)
                service.add_caption(product_id, "زندگی نو، انرژی نو ✨", "occasion", category, 14)
                service.add_caption(product_id, "بهار همیشه قشنگه 🌸", "occasion", category, 15)
                service.add_caption(product_id, "نوروز یعنی لبخند 🌿", "occasion", category, 16)
                service.add_caption(product_id, "سال جدیدت فوق‌العاده باشه ✨", "occasion", category, 17)
                service.add_caption(product_id, "پر از نور باشی 🌸", "occasion", category, 18)
                service.add_caption(product_id, "بهار اومده برای شروعی تازه 🌿", "occasion", category, 19)
                service.add_caption(product_id, "نوروز مبارک ✨💚", "occasion", category, 20)
                total += 20
            elif category == "یلدا":
                service.add_caption(product_id, "یلدا مبارک 🌙 طولانی‌ترین شب، شیرین‌ترین خاطره", "occasion", category, 1)
                service.add_caption(product_id, "شب یلدا یعنی عشق و خانواده ❤️", "occasion", category, 2)
                service.add_caption(product_id, "یلدا یعنی کنار هم بودن 🍉", "occasion", category, 3)
                service.add_caption(product_id, "بلندترین شب سال، گرم‌ترین لحظه‌ها 🌙", "occasion", category, 4)
                service.add_caption(product_id, "یلداتون مبارک ✨", "occasion", category, 5)
                service.add_caption(product_id,"یلدا مبارک دوست من 🌙", "occasion", category, 6)
                service.add_caption(product_id, "زمستون با یلدا قشنگ‌تره 🍉", "occasion", category, 7)
                service.add_caption(product_id, "شب عشق و نور 🌙❤️", "occasion", category, 8)
                service.add_caption(product_id, "کنار هم، گرم‌تر از هر آتشی 🔥", "occasion", category, 9)
                service.add_caption(product_id, "یلدا یعنی خاطره ✨", "occasion", category, 10)
                service.add_caption(product_id, "انار و لبخند 🍉😊", "occasion", category, 11)
                service.add_caption(product_id, "شب طولانی، عشق بی‌پایان ❤️", "occasion", category, 12)
                service.add_caption(product_id, "یلدا مبارک 🌙✨", "occasion", category, 13)
                service.add_caption(product_id, "با هم بودن یعنی یلدا 🍉", "occasion", category, 14)
                service.add_caption(product_id, "گرمای عشق در سردترین شب 🌙", "occasion", category, 15)
                service.add_caption(product_id, "شب قصه‌ها ✨", "occasion", category, 16)
                service.add_caption(product_id, "یلدا یعنی خانواده ❤️", "occasion", category, 17)
                service.add_caption(product_id, "لبخند زیر نور انار 🍉", "occasion", category, 18)
                service.add_caption(product_id, "شب یلدا مبارک 🌙", "occasion", category, 19)
                service.add_caption(product_id, "طولانی‌ترین شب، کوتاه‌ترین فاصله دل‌ها ❤️", "occasion", category, 20)
                total += 20
            elif category == "روز پدر":
                service.add_caption(product_id, "روز پدر مبارک ❤️ قوی‌ترین تکیه‌گاه زندگی", "occasion", category, 1)
                service.add_caption(product_id, "بابا یعنی امنیت، عشق و آرامش 💙", "occasion", category, 2)
                service.add_caption(product_id, "روزت مبارک قهرمان زندگی من 👨‍👧✨", "occasion", category, 3)
                service.add_caption(product_id, "پدر یعنی کوه 💪 روزت مبارک", "occasion", category, 4)
                service.add_caption(product_id, "بهترین تکیه‌گاه دنیا، بابا ❤️", "occasion", category, 5)
                service.add_caption(product_id, "روز پدر مبارک 💙", "occasion", category, 6)
                service.add_caption(product_id, "بودنت یعنی آرامش ❤️ روز پدر مبارک", "occasion", category, 7)
                service.add_caption(product_id, "بابا، اولین قهرمان زندگی 👨‍👧", "occasion", category, 8)
                service.add_caption(product_id, "عشق واقعی اسمش پدره ❤️", "occasion", category, 9)
                service.add_caption(product_id, "روزت مبارک مردی که همیشه هست 💙", "occasion", category, 10)
                total += 10
            elif category == "روز مادر":
                service.add_caption(product_id, "روز مادر مبارک ❤️ فرشته‌ی بی‌نظیر زندگی", "occasion", category, 1)
                service.add_caption(product_id, "مامان یعنی عشق بی‌قید و شرط 💐", "occasion", category, 2)
                service.add_caption(product_id, "بهترین قلب دنیا، قلب مادر ❤️", "occasion", category, 3)
                service.add_caption(product_id, "روزت مبارک فرشته زمینی من 👩‍👧✨", "occasion", category, 4)
                service.add_caption(product_id, "مادر یعنی آرامش بی‌انتها 💖", "occasion", category, 5)
                service.add_caption(product_id, "روز مادر مبارک 💐", "occasion", category, 6)
                service.add_caption(product_id, "همه دنیا خلاصه میشه در آغوش مادر ❤️", "occasion", category, 7)
                service.add_caption(product_id, "مامان یعنی بهشت روی زمین 🌸", "occasion", category, 8)
                service.add_caption(product_id, "عشق یعنی مادر ❤️", "occasion", category, 9)
                service.add_caption(product_id, "روزت مبارک مهربون‌ترین آدم دنیا 💐", "occasion", category, 10)  
                total += 10
            elif category == "روز معلم":
                service.add_caption(product_id, "روز معلم مبارک 🌟 سازنده آینده‌ها", "occasion", category, 1)
                service.add_caption(product_id, "معلم یعنی نور 💡 روزت مبارک", "occasion", category, 2)
                service.add_caption(product_id, "بهترین راهنماهای زندگی، معلم‌ها هستند 📚", "occasion", category, 3)
                service.add_caption(product_id, "روزت مبارک استاد عزیز 🌟", "occasion", category, 4)
                service.add_caption(product_id, "معلم یعنی امید و دانایی 📖", "occasion", category, 5)
                service.add_caption(product_id, "روز معلم مبارک 🍎", "occasion", category, 6)
                service.add_caption(product_id, "با شما دنیا روشن‌تره 🌟", "occasion", category, 7)
                service.add_caption(product_id, "معلم یعنی آینده 📚✨", "occasion", category, 8)
                service.add_caption(product_id, "سپاس از تمام آموزش‌ها 🍎", "occasion", category, 9)
                service.add_caption(product_id, "روزت مبارک سازنده فردا 🌟", "occasion", category, 10)
                total += 10
            elif category == "روز مهندس":
                service.add_caption(product_id, "روز مهندس مبارک ⚙️ سازنده دنیای امروز", "occasion", category, 1)
                service.add_caption(product_id, "مهندس یعنی خلاقیت و منطق 🧠", "occasion", category, 2)
                service.add_caption(product_id, "روزت مبارک سازنده آینده ⚙️", "occasion", category, 3)
                service.add_caption(product_id, "دنیا با شما ساخته میشه 🏗️", "occasion", category, 4)
                service.add_caption(product_id, "مهندس یعنی حل مسئله 🔧", "occasion", category, 5)
                service.add_caption(product_id, f"روز مهندس مبارک {p.name or 'مهندس'} ⚙️", "occasion", category, 6)
                service.add_caption(product_id, "خلاقیت شما دنیا رو می‌سازه 🧠", "occasion", category, 7)
                service.add_caption(product_id, "مهندس یعنی آینده بهتر 🏗️", "occasion", category, 8)
                service.add_caption(product_id, "روزت مبارک ذهن‌های خلاق ⚙️", "occasion", category, 9)
                service.add_caption(product_id, "با شما دنیا دقیق‌تر و بهتره 🔧", "occasion", category, 10)
                total += 10
            elif category == "پیام تسلیت":
                service.add_caption(product_id, "با نهایت تأسف و اندوه تسلیت عرض می‌کنیم 🖤", "occasion", category, 1)
                service.add_caption(product_id, "یادش گرامی و روحش آرام 🕊", "occasion", category, 2)
                service.add_caption(product_id, "تسلیت ما را پذیرا باشید 🖤", "occasion", category, 3)
                service.add_caption(product_id, "در این غم بزرگ شریک هستیم 🕊", "occasion", category, 4)
                service.add_caption(product_id, "خداوند به بازماندگان صبر بدهد 🖤", "occasion", category, 5)
                service.add_caption(product_id, "تسلیت خدمت شما 🖤", "occasion", category, 6)
                service.add_caption(product_id, "روحشان شاد و یادشان جاودان 🕊", "occasion", category, 7)
                service.add_caption(product_id, "غم بزرگی‌ست... تسلیت عرض می‌کنیم 🖤", "occasion", category, 8)
                service.add_caption(product_id, "درگذشت عزیزتان را تسلیت می‌گوییم 🕊", "occasion", category, 9)
                service.add_caption(product_id, "یادشان همیشه در قلب‌ها خواهد ماند 🖤", "occasion", category, 10)
                total += 10

            elif category == "تخفیف":
                service.add_caption(product_id, "فقط امروز! تخفیف ویژه رو از دست نده 🔥", "occasion", category, 1)
                service.add_caption(product_id, "حراج شروع شد! وقت خرید با قیمت عالیه 🛍️", "occasion", category, 2)
                service.add_caption(product_id, "تا 50٪ تخفیف ویژه همین الان ⚡", "occasion", category, 3)
                service.add_caption(product_id, "فرصت محدود ⏳ این تخفیف‌ها برمی‌گردن؟ نه!", "occasion", category, 4)
                service.add_caption(product_id, "حراج بزرگ شروع شد 🔥 سریع‌تر از همه بخر!", "occasion", category, 5)
                service.add_caption(product_id, "قیمت‌ها سقوط کردن 📉 وقتشه خرید کنی!", "occasion", category, 6)
                service.add_caption(product_id, "فقط برای مدت محدود ⏰ تخفیف‌های ویژه فعال شد", "occasion", category, 7)
                service.add_caption(product_id, "این قیمت‌ها واقعی نیستن 😍 ولی الان هستن!", "occasion", category, 8)
                service.add_caption(product_id, "حراجی که نباید از دست بدی 🛍️🔥", "occasion", category, 9)
                service.add_caption(product_id, "تخفیف‌های شوکه‌کننده همین الان فعال شد ⚡", "occasion", category, 10)
                service.add_caption(product_id, "خرید کن قبل از اینکه تموم شه ⏳", "occasion", category, 11)
                service.add_caption(product_id, "قیمت‌ها افتادن پایین‌تر از حد تصور 😍", "occasion", category, 12)
                service.add_caption(product_id, "فروش ویژه فقط برای امروز 🔥", "occasion", category, 13)
                service.add_caption(product_id, "سریع باش! این تخفیف‌ها محدودن ⚡", "occasion", category, 14)
                service.add_caption(product_id, "حراج واقعی یعنی همین 😎🛍️", "occasion", category, 15)
                service.add_caption(product_id, "هرچی زودتر، ارزون‌تر 🔥", "occasion", category, 16)
                service.add_caption(product_id, "فرصت طلایی خرید 💛 همین حالا!", "occasion", category, 17)
                service.add_caption(product_id, "تخفیف‌هایی که باورش سخته 😍", "occasion", category, 18)
                service.add_caption(product_id, "همه چیز زیر قیمت واقعی ⚡", "occasion", category, 19)
                service.add_caption(product_id, "این حراج رو از دست بدی، ضرر کردی 😎", "occasion", category, 20)
                total += 20
            elif category == "بلک فرایدی":
                service.add_caption(product_id, "بلک فرایدی شروع شد 🖤🔥 آماده‌ای؟", "occasion", category, 1)
                service.add_caption(product_id, "بزرگ‌ترین تخفیف سال همینجاست ⚡", "occasion", category, 2)
                service.add_caption(product_id, "Black Friday یعنی خرید هوشمند 😎🛍️", "occasion", category, 3)
                service.add_caption(product_id, "قیمت‌ها سقوط آزاد 📉🔥", "occasion", category, 4)
                service.add_caption(product_id, "فقط یک بار در سال! الان وقتشه ⏳", "occasion", category, 5)
                service.add_caption(product_id, "بلک فرایدی = شکار بهترین قیمت‌ها 🖤", "occasion", category, 6)
                service.add_caption(product_id, "تا 70٪ تخفیف واقعی 😍🔥", "occasion", category, 7)
                service.add_caption(product_id, "سریع‌تر از همه بخر قبل از تموم شدن ⚡", "occasion", category, 8)
                service.add_caption(product_id, "دیگه بهونه‌ای نیست برای نخریدن 😎", "occasion", category, 9)
                service.add_caption(product_id, "Black Friday فقط یک کلمه نیست… یه فرصت طلاییه 🖤", "occasion", category, 10)
                service.add_caption(product_id, "این تخفیف‌ها واقعی‌تر از همیشه‌ان 🔥", "occasion", category, 11)
                service.add_caption(product_id, "خرید کن، بعداً از خودت تشکر می‌کنی 😍", "occasion", category, 12)
                service.add_caption(product_id, "بلک فرایدی یعنی شروع شکار 🖤🛍️", "occasion", category, 13)
                service.add_caption(product_id, "هر ثانیه مهمه ⏳", "occasion", category, 14)
                service.add_caption(product_id, "قیمت‌ها دیوونه شدن 😎🔥", "occasion", category, 15)
                service.add_caption(product_id, "این فرصت دوباره تکرار نمیشه ⚡", "occasion", category, 16)
                service.add_caption(product_id, "Black Friday = خرید بدون پشیمونی 🖤", "occasion", category, 17)
                service.add_caption(product_id, "همه چیز آماده‌ست، فقط تو کم بودی 😍", "occasion", category, 18)
                service.add_caption(product_id, "بیشتر بخر، کمتر پرداخت کن 🔥", "occasion", category, 19)
                service.add_caption(product_id, "بلک فرایدی یعنی بهترین انتخاب‌ها ⚡🛍️", "occasion", category, 20)
                total += 20
            elif category == "محصول جدید":
                service.add_caption(product_id, "محصول جدید رسید 😍 اولین نفر تو باش!", "occasion", category, 1)
                service.add_caption(product_id, "جدیدترین محصول بالاخره رونمایی شد 🔥", "occasion", category, 2)
                service.add_caption(product_id, "همین الان تازه وارد شد ⚡", "occasion", category, 3)
                service.add_caption(product_id, "نو، خاص، متفاوت ✨", "occasion", category, 4)
                service.add_caption(product_id, "اولین تجربه رو از دست نده 😎", "occasion", category, 5)
                service.add_caption(product_id, "محصولی که همه منتظرش بودن 😍", "occasion", category, 6)
                service.add_caption(product_id, "جدید اومده… و خیلی خفنه 🔥", "occasion", category, 7)
                service.add_caption(product_id, "به دنیای جدید خوش آمدی ✨", "occasion", category, 8)
                service.add_caption(product_id, "تازه‌ترین محصول بازار ⚡", "occasion", category, 9)
                service.add_caption(product_id, "این فقط یک محصول نیست… یه تجربه‌ست 😍", "occasion", category, 10)
                service.add_caption(product_id, "اولین نگاه = عاشق شدن ❤️", "occasion", category, 11)
                service.add_caption(product_id, "محصول جدید، سطح جدید 🔥", "occasion", category, 12)
                service.add_caption(product_id, "همین الان معرفی شد 🎉", "occasion", category, 13)
                service.add_caption(product_id, "قبل از همه امتحانش کن 😎", "occasion", category, 14)
                service.add_caption(product_id, "نوآوری واقعی اینجاست ⚡", "occasion", category, 15)
                service.add_caption(product_id, "محصولی که بازی رو عوض می‌کنه 🔥", "occasion", category, 16)
                service.add_caption(product_id, "جدیدترین عضو خانواده 😍", "occasion", category, 17)
                service.add_caption(product_id, "حس متفاوت رو تجربه کن ✨", "occasion", category, 18)
                service.add_caption(product_id, "اولین‌ها همیشه خاص‌ترن 😎", "occasion", category, 19)
                service.add_caption(product_id, "این یکی رو از دست نده ⚡🔥", "occasion", category, 20)
                total += 20
            elif category == "افتتاحیه":     
                service.add_caption(product_id, "بالاخره انتظارها تموم شد 🎉 امروز یک شروع تازه‌ست… یک افتتاحیه بزرگ که قراره کلی اتفاق خوب رو شروع کنه. خوش اومدید به این لحظه خاص ✨", "occasion", category, 1)
                service.add_caption(product_id, "افتتاحیه فقط یک شروع نیست… یک رویاست که واقعی شده 💫 از امروز اینجا قراره بهترین تجربه‌ها ساخته بشه. خوش آمدید ❤️", "occasion", category, 2)
                service.add_caption(product_id, "امروز یه روز معمولی نیست… امروز روز شروع یک مسیر جدیده 🚀 افتتاحیه‌ای که پر از انرژی، امید و اتفاق‌های خوبه ✨", "occasion", category, 3)
                service.add_caption(product_id, "با افتخار اعلام می‌کنیم… اینجا رسماً شروع شد 🎊 جایی برای تجربه‌های متفاوت، لحظه‌های خاص و خاطره‌های ماندگار ❤️", "occasion", category, 4)
                service.add_caption(product_id, "هر شروعی یه داستان داره… و اینجا داستان ما از امروز آغاز شد 📖✨ افتتاحیه‌ای برای ساختن آینده‌ای بهتر", "occasion", category, 5)
                service.add_caption(product_id, "به یک شروع فوق‌العاده خوش آمدید 🎉 امروز فقط یک افتتاحیه نیست، بلکه آغاز یک تجربه خاص و متفاوت است ✨", "occasion", category, 6)
                service.add_caption(product_id, "لحظه‌ای که مدت‌ها منتظرش بودیم بالاخره رسید 💫 افتتاحیه‌ای پر از هیجان، انرژی مثبت و شروعی قدرتمند 🚀", "occasion", category, 7)
                service.add_caption(product_id, "از امروز اینجا فقط یک اسم نیست… یک تجربه‌ست ✨ افتتاحیه‌ای که قراره مسیر جدیدی رو بسازه ❤️", "occasion", category, 8)
                service.add_caption(product_id, "این فقط یک افتتاحیه نیست… این شروع یک مسیر بزرگه 🚀 از امروز همه چیز متفاوت خواهد بود ✨ خوش آمدید ❤️", "occasion", category, 9)
                service.add_caption(product_id, "درهای یک دنیای جدید باز شد 🎊 افتتاحیه‌ای برای شروع بهترین لحظه‌ها، بهترین تجربه‌ها و بهترین خاطره‌ها ✨", "occasion", category, 10)            
                total += 10
            elif category == "دعوت":     
                service.add_caption(product_id, "با کمال احترام و شادی از شما دعوت می‌کنیم در این لحظه خاص کنار ما باشید 🎉 حضورتان باعث افتخار و گرمای این رویداد خواهد بود ✨", "occasion", category, 1)
                service.add_caption(product_id, "دعوتید به یک لحظه متفاوت… جایی که قرار است خاطره‌ها ساخته شوند 💫 خوشحال می‌شویم در کنار ما باشید ❤️", "occasion", category, 2)
                service.add_caption(product_id, "حضور شما برای ما فقط یک همراهی نیست، بلکه بخشی از زیبایی این اتفاق است 🌿 با افتخار دعوت‌تان می‌کنیم ✨", "occasion", category, 3)
                service.add_caption(product_id, "به جمع ما بپیوندید تا با هم لحظه‌ای خاص و به‌یادماندنی بسازیم 🎊 حضور شما ارزشمندترین بخش این رویداد است ❤️", "occasion", category, 4)
                service.add_caption(product_id, "این یک دعوت ساده نیست… یک دعوت به شادی، همراهی و ساختن خاطره‌های ماندگار است ✨ خوشحال می‌شویم کنارمان باشید 💫", "occasion", category, 5)
                service.add_caption(product_id, "با عشق و احترام از شما دعوت می‌کنیم در این رویداد خاص حضور داشته باشید 🌸 بودن شما این لحظه را کامل‌تر می‌کند ❤️", "occasion", category, 6)
                service.add_caption(product_id, "دعوتید به جشنی از جنس لحظه‌های خوب 🎉 حضورتان باعث افتخار ما و زیبایی این جمع خواهد بود ✨", "occasion", category, 7)  
                service.add_caption(product_id, "یک لحظه خاص بدون شما کامل نیست 💫 از شما دعوت می‌کنیم همراه ما در این تجربه زیبا باشید ❤️", "occasion", category, 8)
                service.add_caption(product_id, "این رویداد با حضور شما معنا پیدا می‌کند 🌿 با افتخار از شما دعوت می‌کنیم کنار ما باشید ✨", "occasion", category, 9)
                service.add_caption(product_id, "بیایید کنار هم یک خاطره ماندگار بسازیم 🎊 شما مهمان ویژه این لحظه هستید، خوشحال می‌شویم حضور داشته باشید ❤️", "occasion", category, 10)
                total += 10    

    db.commit()
    print(f"✅ تمام شد! {total} کپشن برای محصولات تولید شد.")


# برای اجرا
if __name__ == "__main__":
    db = next(get_db())   # session خودت
    auto_generate_captions(db, limit=30000)   # می‌تونی عدد را تغییر بدی
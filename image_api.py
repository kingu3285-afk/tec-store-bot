import logging
import re
import urllib.parse

import aiohttp

from config import POLLINATIONS_BASE_URL

logger = logging.getLogger(__name__)

# ==============================================================================
# SYSTEM PROMPT — يُدمج في كل طلب ليوجّه النموذج نحو التفسير البصري الدقيق
# ==============================================================================
VISUAL_SYSTEM_INSTRUCTION = (
    "As a visual scene expert: interpret the following as a photorealistic image description, "
    "focus only on visual elements, ignore non-visual words"
)

QUALITY_SUFFIX = (
    "photorealistic, high quality, cinematic, 8k, highly detailed, sharp focus"
)

# ==============================================================================
# أنماط الكشف
# ==============================================================================
ARABIC_PATTERN = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')

# كشف المقارنة (ضد / مقارنة / مقابل / vs / versus)
VERSUS_PATTERN = re.compile(
    r'^(.+?)\s+(?:ضد|مقارنة\s*(?:بين|مع)?|مقابل|vs\.?|versus)\s+(.+)$',
    re.IGNORECASE | re.UNICODE,
)

# كشف نمط قبل/بعد — يدعم العربية والإنجليزية بصيغ متعددة
BEFORE_AFTER_PATTERN = re.compile(
    r'(?:(.+?)\s+)?(?:قبل\s+وبعد|قبل\s+و\s+بعد|before\s+(?:and\s+)?after)(?:\s+(.+))?',
    re.IGNORECASE | re.UNICODE,
)

# قاموس التحولات الشائعة: الكلمة المفتاحية → (حالة قبل، حالة بعد)
TRANSFORMATION_CONTEXT: dict[str, tuple[str, str]] = {
    # تجديد وبناء
    "التجديد": ("old, worn-out, outdated", "freshly renovated, modern, clean"),
    "تجديد": ("old, worn-out, outdated", "freshly renovated, modern, clean"),
    "renovation": ("old, dilapidated, run-down", "beautifully renovated, modern"),
    "الإصلاح": ("damaged, broken, deteriorated", "fully repaired, restored"),
    "إصلاح": ("damaged, broken", "repaired, restored like new"),
    "البناء": ("empty land, construction site", "completed modern building"),
    # اللياقة والصحة
    "خسارة الوزن": ("overweight, unhealthy body", "slim, fit, athletic body"),
    "فقدان الوزن": ("overweight, heavy body", "slim, toned, healthy body"),
    "weight loss": ("overweight, heavy body", "slim, toned, athletic body"),
    "diet": ("overweight person", "slim fit person after diet"),
    "اللياقة": ("out of shape, unfit body", "muscular, fit, healthy body"),
    "fitness": ("out of shape body", "muscular, toned, athletic body"),
    # تجميل وتصفيف
    "المكياج": ("bare natural face without makeup", "beautifully made-up face with full makeup"),
    "makeup": ("bare natural face", "beautifully made-up glamorous face"),
    "الشعر": ("untidy, dull, damaged hair", "styled, shiny, healthy hair"),
    "hair": ("messy, dull hair", "perfectly styled, shiny, healthy hair"),
    "التصميم": ("plain, undesigned space", "beautifully designed, elegant modern space"),
    "design": ("plain, boring design", "stunning, modern, professional design"),
    # طبيعة وبيئة
    "الزراعة": ("dry, barren, desert land", "lush green fertile farm with crops"),
    "التشجير": ("barren dry land", "lush green forest with trees"),
    "النظافة": ("dirty, messy, cluttered space", "clean, tidy, spotless organized space"),
    "cleaning": ("dirty, messy room", "clean, sparkling, organized room"),
}

# فاصل العناصر في العربية — يدعم الواو ملصقة (وجوال) أو منفصلة (و جوال)
ARABIC_SPLIT_PATTERN = re.compile(
    r'\s+و(?=\S)|\s+و\s+|\s+مع\s+|\s+وكذلك\s+|\s+إلى\s+جانب\s+|\s+بجانب\s+|[،,]\s*'
)

# ==============================================================================
# قاموس المدن والمعالم الجغرافية (عربي + إنجليزي)
# ==============================================================================
CITY_LANDMARKS: dict[str, str] = {
    # السعودية
    "الرياض": "Riyadh city skyline with Kingdom Centre Tower, Al Faisaliah Tower, and King Abdulaziz Road at night",
    "جدة": "Jeddah waterfront Corniche with King Fahd Fountain and Al-Balad historic district at sunset",
    "مكة": "Masjid al-Haram in Mecca with Kaaba and Abraj Al-Bait Towers surrounding it",
    "المدينة": "Al-Masjid an-Nabawi Prophet's Mosque in Medina with its green dome and minarets",
    "الدمام": "Dammam city by the Arabian Gulf coast with King Fahd Causeway",
    "الطائف": "Taif city among rose gardens and mountains in Saudi Arabia",
    "أبها": "Abha mountain city in Asir region with green terraced hills and fog",
    # الإمارات
    "دبي": "Dubai skyline with Burj Khalifa, Palm Jumeirah, and Dubai Marina at golden hour",
    "أبوظبي": "Abu Dhabi with Sheikh Zayed Grand Mosque and Louvre Abu Dhabi on Saadiyat Island",
    "الشارقة": "Sharjah city with Al Noor Mosque and Khalid Lagoon waterfront",
    # دول خليجية أخرى
    "الكويت": "Kuwait City skyline with Kuwait Towers and Liberation Tower by the Gulf",
    "الدوحة": "Doha Qatar skyline with Museum of Islamic Art, The Pearl, and West Bay skyscrapers",
    "المنامة": "Manama Bahrain with Al Fateh Grand Mosque and Bahrain World Trade Center",
    "مسقط": "Muscat Oman with Sultan Qaboos Grand Mosque and rocky mountains by the sea",
    # الوطن العربي
    "القاهرة": "Cairo Egypt with Great Pyramids of Giza, Sphinx, and Nile River at sunset",
    "بيروت": "Beirut Lebanon waterfront Corniche with Pigeon Rocks and city skyline",
    "عمّان": "Amman Jordan with Roman Theatre, Amman Citadel, and city hillsides",
    "بغداد": "Baghdad Iraq with Tigris River, Al-Mutanabbi Street, and the Abbasid Palace",
    "دمشق": "Damascus Syria old city with Umayyad Mosque and Souq al-Hamidiyya",
    "تونس": "Tunis medina with Zitouna Mosque and white-blue architecture",
    "الرباط": "Rabat Morocco with Hassan Tower, Mausoleum of Mohammed V, and Bou Regreg river",
    "الجزائر": "Algiers Algeria white city hillside overlooking the Mediterranean Sea",
    "طرابلس": "Tripoli Libya with Arch of Marcus Aurelius and Mediterranean coastline",
    # مدن دولية شائعة
    "لندن": "London with Big Ben, Tower Bridge, and Thames River on a cloudy day",
    "باريس": "Paris with Eiffel Tower, Louvre Museum, and Seine River at golden hour",
    "نيويورك": "New York City with Statue of Liberty, Empire State Building, and Brooklyn Bridge",
    "طوكيو": "Tokyo with Mount Fuji, Tokyo Skytree, and Shibuya crossing at night",
    "برلين": "Berlin with Brandenburg Gate, Berlin TV Tower, and Spree River",
    "روما": "Rome with Colosseum, Trevi Fountain, and St. Peter's Basilica",
    "إسطنبول": "Istanbul with Hagia Sophia, Blue Mosque, and Bosphorus Strait",
    "موسكو": "Moscow with Red Square, Saint Basil's Cathedral, and Kremlin in winter",
    "بكين": "Beijing with Forbidden City, Great Wall of China, and Tiananmen Square",
    "سيدني": "Sydney with Opera House, Harbour Bridge, and blue harbour at sunrise",
    "ميلانو": "Milan with Duomo di Milano cathedral and Galleria Vittorio Emanuele II",
    "برشلونة": "Barcelona with Sagrada Família, Park Güell, and Mediterranean coastline",
    "سنغافورة": "Singapore with Marina Bay Sands, Gardens by the Bay, and city skyline at night",
    "بانكوك": "Bangkok with Wat Arun temple, Chao Phraya River, and golden temples",
    "مومباي": "Mumbai with Gateway of India, Marine Drive Queen's Necklace at night",
    "نيودلهي": "New Delhi with Taj Mahal, India Gate, and Lotus Temple",
}

# ==============================================================================
# قاموس الترجمة العربي → إنجليزي
# ==============================================================================
ARABIC_PREPOSITIONS: dict[str, str] = {
    " على ": " on ", " فوق ": " on top of ", " تحت ": " under ",
    " بجانب ": " next to ", " بداخل ": " inside ", " في ": " in ",
    " أمام ": " in front of ", " خلف ": " behind ", " حول ": " around ",
    " قرب ": " near ", " بين ": " between ",
}

ARABIC_TO_ENGLISH: dict[str, str] = {
    # أشخاص
    "شخص": "person", "رجل": "man", "امرأة": "woman", "طفل": "child",
    "ولد": "boy", "بنت": "girl", "شاب": "young man", "عجوز": "elderly person",
    # حيوانات
    "قطة": "cat", "كلب": "dog", "أسد": "lion", "نمر": "tiger",
    "فيل": "elephant", "طائر": "bird", "سمكة": "fish", "فراشة": "butterfly",
    "حصان": "horse", "أرنب": "rabbit", "ذئب": "wolf", "دب": "bear",
    "غزال": "deer", "نسر": "eagle", "ببغاء": "parrot",
    # تقنية وإلكترونيات
    "ساعة رولكس": "Rolex luxury watch", "رولكس": "Rolex luxury watch",
    "جوال": "smartphone", "هاتف": "smartphone", "آيفون": "iPhone",
    "لابتوب": "laptop", "كمبيوتر": "computer", "تابلت": "tablet",
    "سماعات": "headphones", "كاميرا": "camera", "تلفزيون": "TV",
    "ساعة": "luxury watch",
    # أثاث وديكور
    "طاولة": "table", "كرسي": "chair", "أريكة": "sofa", "سرير": "bed",
    "مكتب": "desk", "رف": "shelf", "مرآة": "mirror", "لمبة": "lamp",
    "باب": "door", "نافذة": "window", "سجادة": "carpet",
    # طعام وشراب
    "قهوة": "coffee cup", "شاي": "tea", "كوب": "cup", "طبق": "plate",
    "فنجان": "coffee mug", "زجاجة": "bottle", "كيكة": "cake",
    "فاكهة": "fruit", "تفاحة": "apple", "برتقالة": "orange",
    # أماكن طبيعية
    "مدينة": "city", "جبل": "mountain", "بحر": "sea", "غابة": "forest",
    "صحراء": "desert", "نهر": "river", "شاطئ": "beach", "جزيرة": "island",
    "بركان": "volcano", "كهف": "cave", "سهل": "plain", "وادي": "valley",
    # سماء وطبيعة
    "سماء": "sky", "نجوم": "stars", "قمر": "moon", "شمس": "sun",
    "غيوم": "clouds", "قوس قزح": "rainbow", "مطر": "rain", "ثلج": "snow",
    "زهور": "flowers", "وردة": "rose", "شجرة": "tree", "حديقة": "garden",
    # مباني
    "منزل": "house", "جسر": "bridge", "قلعة": "castle", "مسجد": "mosque",
    "برج": "tower", "ناطحة سحاب": "skyscraper", "متجر": "store",
    # مركبات
    "سيارة": "car", "دراجة": "motorcycle", "طائرة": "airplane",
    "قارب": "boat", "قطار": "train", "شاحنة": "truck",
    # أوصاف
    "خيالي": "fantasy", "مستقبلي": "futuristic", "قديم": "ancient",
    "سحري": "magical", "ملون": "colorful", "غامق": "dark", "مضيء": "bright",
    "رومانسي": "romantic", "رعب": "horror", "سلام": "peaceful",
    # فضاء وخرافي
    "فضاء": "space", "كوكب": "planet", "مجرة": "galaxy", "نيزك": "meteor",
    "روبوت": "robot", "تنين": "dragon", "ساحر": "wizard", "مارد": "giant",
    # زمن
    "ليل": "night", "نهار": "daytime", "غروب": "sunset", "شروق": "sunrise",
    "فجر": "dawn", "ظهر": "noon",
    # مواد
    "خشب": "wood", "حجر": "stone", "زجاج": "glass", "معدن": "metal",
    "ذهب": "gold", "فضة": "silver", "رخام": "marble",
    # إكسسوارات
    "حقيبة": "bag", "نظارة": "glasses", "عطر": "perfume bottle",
    "خاتم": "ring", "قلادة": "necklace", "حذاء": "shoes",
}


# ==============================================================================
# دوال المساعدة
# ==============================================================================

def is_arabic(text: str) -> bool:
    return bool(ARABIC_PATTERN.search(text))


def get_city_visual(name: str) -> str:
    """يحوّل اسم مدينة إلى وصف بصري لمعالمها. يعيد الاسم الإنجليزي إن لم يُعرف."""
    stripped = name.strip()
    # بحث مباشر
    if stripped in CITY_LANDMARKS:
        return CITY_LANDMARKS[stripped]
    # بحث جزئي (لو كتب "مدينة الرياض" مثلاً)
    for city_key, landmark in CITY_LANDMARKS.items():
        if city_key in stripped:
            return landmark
    # إن لم يُعرف، نعيد الاسم مترجماً + كلمة city
    translated = translate_arabic(stripped)
    cleaned = " ".join(ARABIC_PATTERN.sub("", translated).split()).strip()
    return f"{cleaned or stripped} city landmarks and skyline"


def translate_arabic(text: str) -> str:
    result = text
    for ar_prep, en_prep in ARABIC_PREPOSITIONS.items():
        result = result.replace(ar_prep, en_prep)
    sorted_vocab = sorted(ARABIC_TO_ENGLISH.items(), key=lambda x: -len(x[0]))
    for arabic_word, english_word in sorted_vocab:
        result = result.replace(arabic_word, english_word)
    return result


def extract_elements(text: str, arabic: bool) -> list[str]:
    if arabic:
        parts = ARABIC_SPLIT_PATTERN.split(text)
    else:
        parts = re.split(r'\s+and\s+|\s+with\s+|\s+alongside\s+|,\s*', text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 1]


def compose_multi_element_prompt(elements: list[str]) -> str:
    if len(elements) == 1:
        return elements[0]
    all_elements = ", ".join(elements)
    return (
        f"a professional studio photograph featuring all of the following objects "
        f"together in one scene: {all_elements}. "
        f"Every single object is clearly visible and in full frame. "
        f"Wide composition showing all items simultaneously, nothing cropped or missing"
    )


# ==============================================================================
# محرك إعادة الصياغة (Intent Rewriter)
# ==============================================================================

def rewrite_versus(left_raw: str, right_raw: str) -> str:
    """يحوّل 'X ضد Y' إلى وصف مشهد split-screen بصري."""
    left_visual = get_city_visual(left_raw) if is_arabic(left_raw) else left_raw.strip()
    right_visual = get_city_visual(right_raw) if is_arabic(right_raw) else right_raw.strip()

    # لو كانت المدن معروفة، نستخدم وصف المعالم؛ وإلا نحوّل عبر القاموس
    if is_arabic(left_visual):
        translated = translate_arabic(left_visual)
        left_visual = " ".join(ARABIC_PATTERN.sub("", translated).split()).strip() or left_visual
    if is_arabic(right_visual):
        translated = translate_arabic(right_visual)
        right_visual = " ".join(ARABIC_PATTERN.sub("", translated).split()).strip() or right_visual

    return (
        f"Split screen image divided by a clean vertical line: "
        f"left side showing {left_visual}, "
        f"right side showing {right_visual}. "
        f"Both sides equal in size, highly detailed, dramatic composition"
    )


def rewrite_before_after(subject_raw: str, transformation_raw: str) -> str:
    """يحوّل 'X قبل وبعد Y' إلى برومت split-screen قبل/بعد."""

    def clean(text: str) -> str:
        if not text:
            return ""
        if is_arabic(text):
            translated = translate_arabic(text)
            return " ".join(ARABIC_PATTERN.sub("", translated).split()).strip() or text
        return text.strip()

    subject = clean(subject_raw) if subject_raw else ""
    transformation = clean(transformation_raw) if transformation_raw else ""

    # ابحث عن التحول في قاموس السياق (بحث مباشر أولاً، ثم جزئي)
    before_state, after_state = "", ""
    lookup_key = transformation_raw.strip() if transformation_raw else ""
    if lookup_key in TRANSFORMATION_CONTEXT:
        before_state, after_state = TRANSFORMATION_CONTEXT[lookup_key]
    else:
        for key, (b, a) in TRANSFORMATION_CONTEXT.items():
            if key in (transformation_raw or "") or key in (subject_raw or ""):
                before_state, after_state = b, a
                break

    # بناء الوصف البصري لكل جانب
    if subject and before_state:
        left_desc = f"{subject}, {before_state}"
        right_desc = f"{subject}, {after_state}"
    elif subject:
        left_desc = f"{subject} in original old state, aged, worn"
        right_desc = f"{subject} after {transformation or 'transformation'}, modern, improved"
    elif transformation:
        left_desc = f"{before_state or 'original state before ' + transformation}"
        right_desc = f"{after_state or 'final result after ' + transformation}"
    else:
        left_desc = "original state, old, worn-out"
        right_desc = "transformed result, new, modern, improved"

    return (
        f"Split screen comparison image with 'BEFORE' label on left and 'AFTER' label on right, "
        f"divided by a clean vertical line: "
        f"left side showing {left_desc}, "
        f"right side showing {right_desc}. "
        f"Dramatic transformation reveal, equal sides, same lighting angle, professional photography"
    )


def detect_and_rewrite(user_prompt: str) -> tuple[str, str]:
    """
    يحلّل نية المستخدم ويعيد (core_prompt, intent_label).
    intent_label: 'versus' | 'before_after' | 'normal'
    """
    stripped = user_prompt.strip()

    # ① كشف نمط قبل/بعد (له الأولوية على المقارنة لتجنب التضارب)
    ba_match = BEFORE_AFTER_PATTERN.match(stripped)
    if ba_match:
        subject_raw = (ba_match.group(1) or "").strip()
        transform_raw = (ba_match.group(2) or "").strip()
        logger.info(f"كُشف نمط قبل/بعد | موضوع: [{subject_raw}] | تحول: [{transform_raw}]")
        return rewrite_before_after(subject_raw, transform_raw), "before_after"

    # ② كشف المقارنة
    vs_match = VERSUS_PATTERN.match(stripped)
    if vs_match:
        left, right = vs_match.group(1).strip(), vs_match.group(2).strip()
        logger.info(f"كُشف نمط مقارنة: [{left}] ضد [{right}]")
        return rewrite_versus(left, right), "versus"

    # ③ معالجة طلب عادي
    return "", "normal"


# ==============================================================================
# بناء البرومت النهائي
# ==============================================================================

def build_prompt(user_prompt: str) -> str:
    arabic = is_arabic(user_prompt)

    # --- مرحلة 1: كشف النية وإعادة الصياغة إن لزم ---
    core, intent = detect_and_rewrite(user_prompt)

    if intent in ("versus", "before_after"):
        final_prompt = f"{VISUAL_SYSTEM_INSTRUCTION}. {core}, {QUALITY_SUFFIX}"
        logger.info(f"[{intent}] البرومت النهائي: {final_prompt}")
        return final_prompt

    # --- مرحلة 2: معالجة طلب عادي (عربي أو إنجليزي) ---
    if arabic:
        logger.info("نص عربي — جاري التحليل والترجمة")
        raw_elements = extract_elements(user_prompt, arabic=True)
        translated_elements = [translate_arabic(el) for el in raw_elements]
        cleaned_elements = [
            " ".join(ARABIC_PATTERN.sub("", el).split()).strip()
            for el in translated_elements
        ]
        cleaned_elements = [el for el in cleaned_elements if el]
        logger.info(f"العناصر: {cleaned_elements}")
        core = compose_multi_element_prompt(cleaned_elements)
    else:
        elements = extract_elements(user_prompt, arabic=False)
        logger.info(f"Elements: {elements}")
        core = compose_multi_element_prompt(elements)

    final_prompt = f"{VISUAL_SYSTEM_INSTRUCTION}. {core}, {QUALITY_SUFFIX}"
    logger.info(f"البرومت النهائي: {final_prompt}")
    return final_prompt


# ==============================================================================
# استدعاء الـ API
# ==============================================================================

class ImageGenerationError(Exception):
    pass


async def generate_image(prompt: str, width: int = 1024, height: int = 1024) -> bytes:
    final_prompt = build_prompt(prompt)
    encoded_prompt = urllib.parse.quote(final_prompt)

    request_url = (
        f"{POLLINATIONS_BASE_URL}/{encoded_prompt}"
        f"?width={width}&height={height}&nologo=true&enhance=true"
    )

    logger.info(f"إرسال طلب | Prompt الأصلي: {prompt}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                request_url, timeout=aiohttp.ClientTimeout(total=90)
            ) as response:
                if response.status != 200:
                    logger.error(f"HTTP {response.status}")
                    raise ImageGenerationError(
                        f"الخدمة أرجعت حالة غير متوقعة: {response.status}"
                    )
                return await response.read()

    except aiohttp.ClientError as e:
        logger.exception("خطأ في الاتصال")
        raise ImageGenerationError(f"تعذر الاتصال بخدمة توليد الصور: {e}")

    except Exception as e:
        logger.exception("خطأ غير متوقع")
        raise ImageGenerationError(f"حدث خطأ غير متوقع: {e}")

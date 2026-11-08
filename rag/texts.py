"""
Every fixed sentence the user can see, in the six languages the website offers.

The LLM writes item answers; everything else a user reads is written here, by code: status
messages, clarify questions, handoff lines and notes. One table per language keeps a
translator's job in one file, and `tests/test_texts.py` checks that every language has every
key with the same placeholders.

English and Korean were written by the team. zh, vi, uz and ru are drafts, like the glossary
and the day tables in rag/schedule_text.py, and need a native-speaker check (PLAN.md §10.4).
A language not listed here gets English.
"""
from __future__ import annotations

import string

LANGUAGES = {"en": "English", "ko": "한국어", "zh": "中文", "vi": "Tiếng Việt",
             "uz": "O'zbekcha", "ru": "Русский"}
DEFAULT_LANG = "en"

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "OUT_OF_SCOPE": "I can only help with household waste in Korea: which bin an item goes "
                        "in, and when and where to put waste out in your district.",
        "INSUFFICIENT_CONTEXT": "I could not find this in the official sources I use, so I "
                                "will not guess.",
        "CLARIFY": "I need one more detail to answer.",
        "SCHEDULE_VARIES": "Collection days differ between collection points in this area, so "
                           "I will not give you one day. Your district office can tell you "
                           "which point is yours.",
        "ITEM_FAILED": "I could not confirm how to throw away this item from the official "
                       "guides, so this answer covers only the collection schedule.",
        "SCHEDULE_FAILED": "I could not find the collection schedule for your area in the "
                           "district data.",
        "contact_phone": "Call {office} ({phone}).",
        "contact_none": "Ask your district office (구청) or community service centre (주민센터).",
        "checked_guides": "national sorting guides (2018 guideline, 2026 rules)",
        "checked_district": "district collection data for {place}",
        "clarify_district": "Which district (구) and neighbourhood (동) do you live in? "
                            "Collection days depend on the area.",
        "clarify_province": "'{district}' exists in {n} provinces. Which one do you mean?",
        "clarify_zones": "{district} has {n} collection zones. Which neighbourhood (동) do you "
                         "live in?",
        "clarify_names": "Which of these do you live in: {dong}?",
        "note_2018": "Based on the 2018 national guideline; your district may have newer local "
                     "rules.",
        "note_2026": "Uses the 2026 national rule (분리수거 등에 관한 지침, effective 2026-01-01).",
        "note_stale": "The district data is dated {date} (more than a year old). Please confirm "
                      "with the office.",
        "note_matches": "'{dong}' matches {n} zones ({names}). Check which one is your exact "
                        "neighbourhood.",
        "note_points": "'{dong}' has {n} collection points. Check which one is yours.",
        "note_not_found": "Neighbourhood '{dong}' was not found; showing all {n} zones of the "
                          "district.",
        "note_zones": "{n} zones; the schedule depends on the neighbourhood.",
        "UNAVAILABLE": "The assistant is not available right now. Please try again in a moment, or ask your district office.",
        "OFFLINE": "Offline demo: this is a recorded example answer, not an answer to your question.",
    },
    "ko": {
        "OUT_OF_SCOPE": "저는 한국의 생활폐기물 분리배출(품목별 배출 방법, 지역별 배출 요일·시간·장소)만 "
                        "안내할 수 있습니다.",
        "INSUFFICIENT_CONTEXT": "제가 사용하는 공식 자료에서 이 내용을 찾지 못해 추측하지 않겠습니다.",
        "CLARIFY": "답변을 위해 정보가 하나 더 필요합니다.",
        "SCHEDULE_VARIES": "이 지역은 배출 장소마다 수거 요일이 달라 한 가지 요일로 안내하지 않겠습니다. "
                           "이용하시는 배출 장소는 구청이나 군청에 문의해 주세요.",
        "ITEM_FAILED": "공식 지침에서 이 물건의 배출 방법을 확인하지 못해, 아래에는 배출 일정만 안내합니다.",
        "SCHEDULE_FAILED": "지역 배출 자료에서 거주하시는 지역의 배출 일정을 찾지 못했습니다.",
        "contact_phone": "{office}({phone})에 문의하세요.",
        "contact_none": "구청이나 주민센터에 문의하세요.",
        "checked_guides": "전국 분리배출 지침(2018년 지침, 2026년 규정)",
        "checked_district": "{place} 지역 배출 자료",
        "clarify_district": "어느 구와 동에 사시나요? 배출 요일은 지역마다 다릅니다.",
        "clarify_province": "'{district}'은(는) {n}개 시·도에 있습니다. 어느 지역인가요?",
        "clarify_zones": "{district}에는 수거 구역이 {n}개 있습니다. 어느 동에 사시나요?",
        "clarify_names": "다음 중 어디에 사시나요: {dong}?",
        "note_2018": "2018년 전국 지침에 따른 안내입니다. 거주하시는 지역에 더 새로운 규정이 있을 수 "
                     "있습니다.",
        "note_2026": "2026년 전국 규정(분리수거 등에 관한 지침, 2026-01-01 시행)을 따릅니다.",
        "note_stale": "지역 자료 기준일이 {date}입니다(1년 이상 경과). 구청에 확인해 주세요.",
        "note_matches": "'{dong}'에 해당하는 구역이 {n}개입니다({names}). 정확한 동을 확인해 주세요.",
        "note_points": "'{dong}'에는 배출 장소가 {n}곳 있습니다. 이용하시는 장소를 확인해 주세요.",
        "note_not_found": "'{dong}'을(를) 찾지 못해 이 구의 전체 {n}개 구역을 보여 드립니다.",
        "note_zones": "구역이 {n}개이며, 배출 일정은 동마다 다릅니다.",
        "UNAVAILABLE": "지금은 안내를 할 수 없습니다. 잠시 후 다시 시도하시거나 구청에 문의해 주세요.",
        "OFFLINE": "오프라인 데모: 질문에 대한 답이 아니라 미리 기록된 예시 답변입니다.",
    },
    "zh": {
        "OUT_OF_SCOPE": "我只能解答韩国生活垃圾的问题：物品应该扔进哪个垃圾桶，以及在您所在的地区"
                        "何时、何地扔垃圾。",
        "INSUFFICIENT_CONTEXT": "我在所使用的官方资料中没有找到相关信息，所以不会猜测。",
        "CLARIFY": "我还需要一条信息才能回答。",
        "SCHEDULE_VARIES": "该地区不同收集点的收集日期不同，所以我不会只告诉您一个日期。"
                           "您所在区的区政府可以告诉您属于哪个收集点。",
        "ITEM_FAILED": "我无法根据官方指南确认这件物品的丢弃方法，所以本回答只包含收集时间。",
        "SCHEDULE_FAILED": "我在地区数据中没有找到您所在地区的收集时间。",
        "contact_phone": "请致电{office}（{phone}）。",
        "contact_none": "请咨询您所在的区政府（구청）或居民中心（주민센터）。",
        "checked_guides": "全国垃圾分类指南（2018年指南、2026年规定）",
        "checked_district": "{place}的地区收集数据",
        "clarify_district": "您住在哪个区（구）和哪个洞（동）？收集日期因地区而异。",
        "clarify_province": "'{district}'在{n}个省市都有。您指的是哪一个？",
        "clarify_zones": "{district}有{n}个收集区域。您住在哪个洞（동）？",
        "clarify_names": "您住在以下哪个地方：{dong}？",
        "note_2018": "依据2018年全国指南；您所在的地区可能有更新的地方规定。",
        "note_2026": "采用2026年全国规定（분리수거 등에 관한 지침，2026-01-01起施行）。",
        "note_stale": "地区数据的日期为{date}（已超过一年）。请向区政府确认。",
        "note_matches": "'{dong}'对应{n}个区域（{names}）。请确认您所在的具体洞。",
        "note_points": "'{dong}'有{n}个收集点。请确认哪个是您的。",
        "note_not_found": "未找到'{dong}'，显示该区全部{n}个区域。",
        "note_zones": "共有{n}个区域；收集时间因洞而异。",
        "UNAVAILABLE": "助手暂时无法使用。请稍后再试，或咨询您所在的区政府。",
        "OFFLINE": "离线演示：这是预先记录的示例回答，并非针对您的问题。",
    },
    "vi": {
        "OUT_OF_SCOPE": "Tôi chỉ có thể giúp về rác thải sinh hoạt ở Hàn Quốc: đồ vật nào bỏ vào "
                        "thùng nào, và khi nào, ở đâu để bỏ rác trong khu vực của bạn.",
        "INSUFFICIENT_CONTEXT": "Tôi không tìm thấy thông tin này trong các nguồn chính thức mà "
                                "tôi sử dụng, nên tôi sẽ không đoán.",
        "CLARIFY": "Tôi cần thêm một thông tin để trả lời.",
        "SCHEDULE_VARIES": "Ngày thu gom khác nhau giữa các điểm thu gom trong khu vực này, nên "
                           "tôi sẽ không đưa ra một ngày duy nhất. Văn phòng quận có thể cho bạn "
                           "biết điểm nào là của bạn.",
        "ITEM_FAILED": "Tôi không xác nhận được cách bỏ món đồ này từ hướng dẫn chính thức, nên "
                       "câu trả lời này chỉ có lịch thu gom.",
        "SCHEDULE_FAILED": "Tôi không tìm thấy lịch thu gom cho khu vực của bạn trong dữ liệu "
                           "của quận.",
        "contact_phone": "Hãy gọi {office} ({phone}).",
        "contact_none": "Hãy hỏi văn phòng quận (구청) hoặc trung tâm dịch vụ cộng đồng (주민센터).",
        "checked_guides": "hướng dẫn phân loại rác toàn quốc (hướng dẫn 2018, quy định 2026)",
        "checked_district": "dữ liệu thu gom của quận cho {place}",
        "clarify_district": "Bạn sống ở quận (구) và phường (동) nào? Ngày thu gom tùy theo khu "
                            "vực.",
        "clarify_province": "'{district}' có ở {n} tỉnh/thành phố. Bạn muốn nói nơi nào?",
        "clarify_zones": "{district} có {n} khu vực thu gom. Bạn sống ở phường (동) nào?",
        "clarify_names": "Bạn sống ở nơi nào sau đây: {dong}?",
        "note_2018": "Dựa trên hướng dẫn quốc gia năm 2018; quận của bạn có thể có quy định địa "
                     "phương mới hơn.",
        "note_2026": "Theo quy định quốc gia năm 2026 (분리수거 등에 관한 지침, có hiệu lực từ "
                     "2026-01-01).",
        "note_stale": "Dữ liệu của quận có ngày {date} (đã hơn một năm). Vui lòng xác nhận lại "
                      "với văn phòng.",
        "note_matches": "'{dong}' khớp với {n} khu vực ({names}). Hãy kiểm tra chính xác phường "
                        "của bạn.",
        "note_points": "'{dong}' có {n} điểm thu gom. Hãy kiểm tra điểm nào là của bạn.",
        "note_not_found": "Không tìm thấy '{dong}'; hiển thị tất cả {n} khu vực của quận.",
        "note_zones": "Có {n} khu vực; lịch thu gom tùy theo phường.",
        "UNAVAILABLE": "Trợ lý hiện không hoạt động. Vui lòng thử lại sau ít phút hoặc hỏi văn phòng quận.",
        "OFFLINE": "Bản demo ngoại tuyến: đây là câu trả lời mẫu đã ghi sẵn, không phải câu trả lời cho câu hỏi của bạn.",
    },
    "uz": {
        "OUT_OF_SCOPE": "Men faqat Koreyadagi maishiy chiqindilar bo'yicha yordam bera olaman: "
                        "buyum qaysi idishga tashlanadi va hududingizda chiqindini qachon va "
                        "qayerga chiqarish kerak.",
        "INSUFFICIENT_CONTEXT": "Men foydalanadigan rasmiy manbalarda bu ma'lumotni topa "
                                "olmadim, shuning uchun taxmin qilmayman.",
        "CLARIFY": "Javob berish uchun yana bitta ma'lumot kerak.",
        "SCHEDULE_VARIES": "Bu hududda yig'ish kunlari yig'ish joylariga qarab farq qiladi, "
                           "shuning uchun bitta kunni aytmayman. Tuman idorangiz qaysi joy "
                           "sizniki ekanini aytib bera oladi.",
        "ITEM_FAILED": "Rasmiy qo'llanmalardan bu buyumni qanday tashlashni aniqlay olmadim, "
                       "shuning uchun bu javobda faqat yig'ish jadvali bor.",
        "SCHEDULE_FAILED": "Tuman ma'lumotlarida hududingiz uchun yig'ish jadvalini topa "
                           "olmadim.",
        "contact_phone": "Qo'ng'iroq qiling: {office} ({phone}).",
        "contact_none": "Tuman idorasi (구청) yoki aholiga xizmat ko'rsatish markazi (주민센터) "
                        "bilan bog'laning.",
        "checked_guides": "umummilliy saralash qo'llanmalari (2018-yil qo'llanmasi, 2026-yil "
                          "qoidalari)",
        "checked_district": "{place} uchun tuman yig'ish ma'lumotlari",
        "clarify_district": "Qaysi tuman (구) va mahallada (동) yashaysiz? Yig'ish kunlari "
                            "hududga bog'liq.",
        "clarify_province": "'{district}' {n} ta viloyatda bor. Qaysi birini nazarda "
                            "tutyapsiz?",
        "clarify_zones": "{district}da {n} ta yig'ish hududi bor. Qaysi mahallada (동) "
                         "yashaysiz?",
        "clarify_names": "Quyidagilardan qaysi birida yashaysiz: {dong}?",
        "note_2018": "2018-yilgi umummilliy qo'llanmaga asoslangan; tumaningizda yangiroq "
                     "mahalliy qoidalar bo'lishi mumkin.",
        "note_2026": "2026-yilgi umummilliy qoida asosida (분리수거 등에 관한 지침, 2026-01-01 "
                     "dan kuchga kirgan).",
        "note_stale": "Tuman ma'lumotlari {date} sanasiga tegishli (bir yildan ko'proq vaqt "
                      "oldin). Iltimos, idoradan aniqlang.",
        "note_matches": "'{dong}' {n} ta hududga mos keladi ({names}). Aniq mahallangizni "
                        "tekshiring.",
        "note_points": "'{dong}'da {n} ta yig'ish joyi bor. Qaysi biri sizniki ekanini "
                       "tekshiring.",
        "note_not_found": "'{dong}' topilmadi; tumanning barcha {n} ta hududi ko'rsatilmoqda.",
        "note_zones": "{n} ta hudud bor; jadval mahallaga bog'liq.",
        "UNAVAILABLE": "Yordamchi hozir ishlamayapti. Birozdan keyin qayta urinib ko'ring yoki tuman idorasiga murojaat qiling.",
        "OFFLINE": "Oflayn demo: bu sizning savolingizga javob emas, oldindan yozib olingan namuna javob.",
    },
    "ru": {
        "OUT_OF_SCOPE": "Я могу помочь только с бытовыми отходами в Корее: в какой контейнер "
                        "выбросить вещь, а также когда и куда выносить мусор в вашем районе.",
        "INSUFFICIENT_CONTEXT": "Я не нашёл этого в официальных источниках, которые использую, "
                                "поэтому не буду гадать.",
        "CLARIFY": "Чтобы ответить, мне нужна ещё одна деталь.",
        "SCHEDULE_VARIES": "В этом районе дни вывоза различаются в зависимости от пункта сбора, "
                           "поэтому я не буду называть один день. В администрации вашего района "
                           "подскажут, какой пункт ваш.",
        "ITEM_FAILED": "Я не смог подтвердить по официальным руководствам, как выбрасывать эту "
                       "вещь, поэтому в ответе только график вывоза.",
        "SCHEDULE_FAILED": "Я не нашёл график вывоза для вашего района в районных данных.",
        "contact_phone": "Позвоните: {office} ({phone}).",
        "contact_none": "Обратитесь в администрацию района (구청) или в центр обслуживания "
                        "жителей (주민센터).",
        "checked_guides": "национальные правила сортировки (руководство 2018 года, правила "
                          "2026 года)",
        "checked_district": "районные данные о вывозе для {place}",
        "clarify_district": "В каком районе (구) и квартале (동) вы живёте? Дни вывоза зависят "
                            "от района.",
        "clarify_province": "'{district}' есть в {n} провинциях. Какой вы имеете в виду?",
        "clarify_zones": "В {district} {n} зон вывоза. В каком квартале (동) вы живёте?",
        "clarify_names": "Где из этого вы живёте: {dong}?",
        "note_2018": "По национальному руководству 2018 года; в вашем районе могут действовать "
                     "более новые местные правила.",
        "note_2026": "По национальному правилу 2026 года (분리수거 등에 관한 지침, действует с "
                     "2026-01-01).",
        "note_stale": "Данные района датированы {date} (больше года назад). Пожалуйста, "
                      "уточните в администрации.",
        "note_matches": "'{dong}' соответствует {n} зонам ({names}). Уточните ваш точный "
                        "квартал.",
        "note_points": "В '{dong}' {n} пунктов сбора. Уточните, какой ваш.",
        "note_not_found": "'{dong}' не найден; показаны все {n} зон района.",
        "note_zones": "{n} зон; график зависит от квартала.",
        "UNAVAILABLE": "Помощник сейчас недоступен. Попробуйте чуть позже или обратитесь в администрацию района.",
        "OFFLINE": "Офлайн-демо: это заранее записанный пример ответа, а не ответ на ваш вопрос.",
    },
}


def lang_or_default(lang: str | None) -> str:
    return lang if lang in TEXTS else DEFAULT_LANG


def text(key: str, lang: str | None, **args) -> str:
    """The sentence `key` in `lang` (English if the language is not offered)."""
    return TEXTS[lang_or_default(lang)][key].format(**args)


def placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}

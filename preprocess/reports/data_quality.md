# Data quality report

Built 2026-11-06T00:17:14+09:00 by `python -m preprocess.build_all`. Numbers for the report (Anar).

## Item chunks (`preprocess/item_chunks.jsonl`)

- 403 chunks: item 293, faq 36, guide 20, rule 42, note 3, table 9
- IDs: UUIDv5 of source + chunker + span + text digest; old IDs kept as `legacy_id`. All checks pass: True (ids_unique, legacy_ids_unique, text_non_empty, metadata_flat, source_present, no_reserved_keys)
- Text length: mean 166.3 characters, max 1265
- 9 `table` chunks transcribed by hand from the 2018 guide p.17-18 (food-waste tables), because PDF extraction loses the table layout. Source wording kept; editor search words are labelled.

## District schedule (`preprocess/schedule.csv`)

- 10187 rows, 222 districts in 16 provinces
- District names in several provinces (need the province): 고성군 (2), 남구 (4), 동구 (5), 북구 (4), 서구 (4), 중구 (5), 강서구 (2)
- Seoul districts with no data: 도봉구, 강동구
- District names fixed: {'동두천 -> 동두천시': 1, '남양주 -> 남양주시': 7, '없음 -> 세종시': 7}; rows with district '없음': 0
- Whole-district rows ('전체', '16개동'): 37; rows with area notes ('… 제외'): 947; rows without area names: 29
- Rows with irregular days ('기타'): 88; rows without phone: 3
- Data dates by year: 2019: 6, 2020: 2151, 2021: 43, 2022: 61, 2023: 339, 2024: 2849, 2025: 977, 2026: 3761
- Rows older than 1 year (flagged `오래된데이터`): 6234 (61%); median age 843 days
- 6072 area names in `dong_lookup.json`; 229 map to more than one district (the assistant must ask)
- 1723 romanised district aliases (`district_aliases.json`)
- Place types: 문전수거 1155, 거점수거 8987, 기타 45

## Glossary (`preprocess/glossary.json`)

- 32 terms in ko/en/zh/vi/uz/ru; bins valid: True; needs a native-speaker check: zh, vi, uz, ru

## Not included

- data.go.kr recycling item API (~770 items): needs an API key; take a dated snapshot, never call it live
- schedules for Seoul 도봉구 and 강동구: not in the national CSV

# Korean Waste Policy Data Preparation

## What I prepared

I prepared Korean waste-disposal policy data so that it can be used more easily by the GenAI application. The original data is a large government-style CSV file, so I cleaned each row and converted it into a readable text chunk. These chunks can then be searched or passed to the language model when a user asks about waste disposal.

The main files in this folder are:

- `utils.py`: Functions for reading, cleaning, and converting the data.
- `output/chunks.jsonl`: The cleaned waste-policy chunks.
- `output/dong_lookup.json`: A fast lookup table for Korean dong names.
- `EDA.ipynb`: The notebook where I run the data-preparation process.

## 1. Raw data: `data/raw/korean_waste_policies.csv`

The raw data contains **10,187 rows**. Each row represents one waste-disposal policy for a local area. The file is written in Korean and uses **CP949 encoding**, so it cannot always be opened correctly as UTF-8.

The raw columns include:

- Local government information: province, district, management number, and management area.
- Area information: the dongs or neighborhoods covered by the policy.
- General waste: disposal method, disposal days, and disposal time.
- Food waste: disposal method, disposal days, and disposal time.
- Recyclables: disposal method, disposal days, and disposal time.
- Bulky waste: disposal method and disposal location.
- Exceptions: days when waste is not collected.
- Contact information: responsible department and telephone number.
- Data information: reference date, update type, and update timestamps.

For example, one raw row can contain values such as:

```text
District: 종로구
General waste method: 규격봉투에 넣어 지정된 요일에 배출
General waste days: 일+월+화+수+목+금
General waste time: 19:00 - 21:00
Food waste method: 물기를 최대한 줄여 음식물만 전용봉투에 넣어 배출
Bulky waste method: 주민센터방문 혹은 종로구홈페이지에 신청 후 배출
Contact: 청소행정과 / 02-2148-2373
```

The raw data is useful, but it is not ideal to send directly to the model because the column names are difficult to read, some values are empty or duplicated, and several values use compact formats such as `월+수+금` or `1900`.

## 2. How I built the chunks: `notebooks/schedule_eda/utils.py`

I built the chunking process in `utils.py`. My main idea is to turn **one policy row into one chunk** so that the disposal method, days, times, area, and contact information stay together.

Before creating the chunk, I clean and standardize the raw values. For example, I convert `월+수+금` into `월, 수, 금`, format times such as `1900` as `19:00`, separate dong names, and replace missing values with clear text such as `정보 없음`.

The output is a readable Korean text document with an ID and metadata:

```text
[서울특별시 종로구] 쓰레기 배출 안내
배출장소: 문전수거 / 집앞
생활쓰레기: 규격봉투에 넣어 지정된 요일에 배출 / 요일: 일, 월, 화, 수, 목, 금 / 시간: 19:00~21:00
음식물쓰레기: 물기를 최대한 줄여 음식물만 전용봉투에 넣어 배출 / 요일: 일, 월, 화, 수, 목, 금 / 시간: 19:00~21:00
재활용품: 투명한 비닐봉투에 담거나 끈으로 묶어서 지정된 요일에 배출 / 요일: 일, 월, 화, 수, 목, 금 / 시간: 19:00~21:00
대형폐기물: 주민센터방문 혹은 종로구홈페이지에 신청 후 배출 / 장소: 집앞
미수거일: 토, 구정연휴, 추석연휴
문의: 청소행정과 (02-2148-2373)
데이터 기준일: 2020-07-10
주의: 오래된 데이터: 2020-07-10 기준
```

Each chunk has:

- `id`: A unique policy ID made from the management number.
- `text`: The readable policy information used for search and prompting.
- `metadata`: Province, district, zone, all area names, collection place, phone number, data date, and an old-data warning.

I save the chunks in `output/chunks.jsonl`, with one JSON object per line. The current output contains **10,187 chunks**.

## 3. What `dong_lookup.json` is

`dong_lookup.json` is an index that maps an area name to all policy chunks that may apply to it. I create it with `build_dong_lookup()`.

For example:

```json
{
  "사근동": [
    {
      "province": "서울특별시",
      "district": "성동구",
      "zone": "2권역",
      "chunk_id": "waste_202030300000400002"
    }
  ]
}
```

This allows the application to find a relevant chunk quickly when a user asks about an area, such as “When can I dispose of food waste in Sageun-dong?”. The regenerated lookup contains **4,779 area names** and keeps all matching policy records.

Some area names can appear in more than one province or district, so the value is a list rather than a single object. The application should filter by `(province, district)` when the user provides that information. If multiple matches remain, it should ask the user to clarify their location.

## 4. Profiling problems and fixes

I checked the source data and found several issues that could affect retrieval and answer quality. I fixed the issues that belong in `utils.py` and documented the remaining limitations below.

### 1. Area names were being lost

The old `split_dongs()` function kept only names ending in `동`. This removed valid areas ending in `읍`, `면`, `리`, `가`, and `로`, and it also removed district-wide labels and areas containing notes.

I changed the function so it now:

- Keeps all named area formats instead of filtering by the `동` suffix.
- Expands compact names such as `휘경1,2동` into `휘경1동` and `휘경2동`.
- Preserves parenthetical notes and district-wide descriptions.
- Normalizes separators such as `+`, `,`, `ㆍ`, and `·`.

### 2. Province was missing from chunk metadata

District names are not globally unique. For example, names such as `중구`, `동구`, `서구`, `남구`, `북구`, `강서구`, and `고성군` can exist in multiple provinces.

I added `province` to every chunk and lookup record. The application should use `(province, district)` rather than the district name alone.

### 3. Some area names are ambiguous

The same neighborhood or area name can map to multiple districts. The lookup now returns **all matches**, including province, district, zone, and chunk ID. The application should ask a clarifying question instead of selecting one result silently.

### 4. Some data dates are old

Around 21% of the source rows use reference dates from 2019–2020. I kept `data_date` in the chunk and added `data_age_warning` metadata. Chunks older than one year also include a warning in the text, so the application can tell the user that the schedule may need verification.

### 5. Some Seoul districts are not present

The source CSV has no schedule rows for Gangdong-gu or Dobong-gu. This is a source-data limitation, not a cleaning error. If a user asks about one of these districts, the application should explicitly say that no schedule data is available instead of guessing.

### 6. Many rows are near-duplicates

Many policies use almost the same template and differ mainly by location. Embedding search alone may retrieve the wrong district. For schedule questions, I should use the structured lookup with province, district, area, and chunk ID first, and use vector search only as a secondary method when appropriate.

### 7. The CSV has limited item-level information

Only a small number of rows mention specific waste items. This CSV is mainly a local schedule dataset, so it cannot reliably answer questions such as “Which bin should I use for batteries?” Item-specific questions should use the national waste-guide data instead.

## 5. Frequently asked questions

This dataset can answer questions about **where, how, when, and who to contact** for waste disposal. Users should usually provide a district or dong name.

### Questions about general waste

- “How should I dispose of general waste in Jongno-gu?”
- “Which days can I dispose of general waste in Jongno-gu?”
- “What time can I put out general waste in Jongno-gu?”
- “How and when should I dispose of general waste in Sageun-dong?”

### Questions about food waste

- “Which bag or container should I use for food waste?”
- “When can I dispose of food waste in Jung-gu?”
- “What time can I put out food waste in my neighborhood?”
- “Can I put food waste outside my home?”

### Questions about recycling

- “How should I separate and dispose of recyclable items?”
- “Which days can I dispose of recyclable items in Yongsan-gu?”
- “What time should I put out recyclable items?”
- “How should I dispose of recyclable items in my neighborhood?”

### Questions about bulky waste

- “How should I report and dispose of bulky waste?”
- “Where should I put out bulky waste in Jongno-gu?”
- “What are the disposal method and location for bulky waste?”

### Questions about collection exceptions and contact information

- “Which days is waste not collected?”
- “What are the non-collection days in this area?”
- “Which department should I contact about waste disposal?”
- “What is the phone number for the waste management department in this area?”

### Questions using a dong name

- “How should I dispose of waste in Sageun-dong?”
- “When can I dispose of food waste in Haengdang 1-dong?”
- “What time can I put out recyclable items in Geumho 1-ga-dong?”

The dataset may not answer questions that are unrelated to local waste-disposal policies, such as the current weather, waste fees that are not included in the source, or a location that does not exist in the lookup. In those cases, the application should not guess and should ask for a district or dong name.

The data reference date is included in every chunk, so the application can also tell the user when the policy information was last based on the source data.
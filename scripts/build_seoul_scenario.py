"""Build an English-readable, explicitly hypothetical Seoul LP input set."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from ko_pron import romanise


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
SCENARIO = ROOT / "data" / "scenario"
PERIOD_START = "2026-11-01"
PERIOD_END = "2026-11-30"
SCENARIO_SOURCE = "SCENARIO-SEOUL-2026-11"
HANGUL_RUN = re.compile(r"[\uac00-\ud7a3]+")
FLOOR = re.compile(r"(\d+)\s*층")
DISTRICT = re.compile(r"([\uac00-\ud7a3]+)구")
DONG = re.compile(r"([\uac00-\ud7a3]+)동")

DISTRICTS = {
    "강남구": "Gangnam-gu",
    "강동구": "Gangdong-gu",
    "강북구": "Gangbuk-gu",
    "강서구": "Gangseo-gu",
    "관악구": "Gwanak-gu",
    "광진구": "Gwangjin-gu",
    "구로구": "Guro-gu",
    "금천구": "Geumcheon-gu",
    "노원구": "Nowon-gu",
    "도봉구": "Dobong-gu",
    "동대문구": "Dongdaemun-gu",
    "동작구": "Dongjak-gu",
    "마포구": "Mapo-gu",
    "서대문구": "Seodaemun-gu",
    "서초구": "Seocho-gu",
    "성동구": "Seongdong-gu",
    "성북구": "Seongbuk-gu",
    "송파구": "Songpa-gu",
    "양천구": "Yangcheon-gu",
    "영등포구": "Yeongdeungpo-gu",
    "용산구": "Yongsan-gu",
    "은평구": "Eunpyeong-gu",
    "종로구": "Jongno-gu",
    "중구": "Jung-gu",
    "중랑구": "Jungnang-gu",
}

ORGANIZATION_TRANSLATIONS = {
    "전국푸드뱅크": "Korea National Food Bank",
    "서울시광역푸드뱅크": "Seoul Metropolitan Food Bank",
}


def english_location(value: str) -> str:
    """Translate Seoul and district labels; romanize remaining proper names."""
    text = value.replace("서울특별시", "Seoul").replace("서울", "Seoul")
    for korean, english in DISTRICTS.items():
        text = text.replace(korean, english)
    text = FLOOR.sub(r" Floor \1", text)
    text = DONG.sub(
        lambda match: f"{romanise(match.group(1), 'rr').title()}-dong",
        text,
    )
    text = DISTRICT.sub(
        lambda match: f"{romanise(match.group(1), 'rr').title()}-gu",
        text,
    )
    text = HANGUL_RUN.sub(lambda match: romanise(match.group(), "rr").title(), text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def english_name(value: str, *, organization: bool = False) -> str:
    """Translate generic organization terms and romanize proper-name components."""
    if organization and value in ORGANIZATION_TRANSLATIONS:
        return ORGANIZATION_TRANSLATIONS[value]
    text = value.replace("(주)", "Co., Ltd.").replace("㈜", "Co., Ltd.")
    if organization:
        text = (
            text.replace("푸드뱅크", "Food Bank ")
            .replace("푸드마켓", "Food Market ")
            .replace("마켓센터", "Market Center")
            .replace("센터", "Center")
        )
    text = text.replace("역점", " Station Branch")
    text = re.sub(
        r"([\uac00-\ud7a3]+)점(?=$|[\s,)C])",
        lambda match: f"{romanise(match.group(1), 'rr').title()} Branch",
        text,
    )
    text = HANGUL_RUN.sub(lambda match: romanise(match.group(), "rr").title(), text)
    return re.sub(r"\s+", " ", text).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write an empty dataset: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def deduplicate_restaurants(
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        address = row["road_address"] or row["lot_address"]
        key = (row["business_name"], address, row["administrative_locality"])
        grouped[key].append(row)

    selected = [
        max(group, key=lambda row: (row["source_reference_date"], row["observation_id"]))
        for group in grouped.values()
    ]
    return sorted(selected, key=lambda row: row["observation_id"])


def main() -> None:
    restaurant_rows = deduplicate_restaurants(
        read_csv(PROCESSED / "korea_seoul_restaurant_waste_observations.csv")
    )
    receiver_rows = [
        row
        for row in read_csv(PROCESSED / "korea_foodbank_sites.csv")
        if row["administrative_area"].startswith("서울")
    ]
    if not restaurant_rows or not receiver_rows:
        raise ValueError("The Seoul scenario requires both restaurant and receiver rows.")

    translated_restaurants = []
    senders = []
    total_supply = Decimal("0")
    for row in restaurant_rows:
        quantity = Decimal(row["raw_reported_discharge_quantity"])
        total_supply += quantity
        name_en = english_name(row["business_name"])
        address = row["road_address"] or row["lot_address"]
        address_en = english_location(address)
        translated_restaurants.append(
            {
                "sender_id": row["observation_id"],
                "business_name_en_romanized": name_en,
                "business_name_original_ko": row["business_name"],
                "business_type_en": "Restaurant",
                "administrative_locality_en": english_location(
                    row["administrative_locality"]
                ),
                "address_en_romanized": address_en,
                "address_original_ko": address,
                "reported_expected_food_waste_kg_per_month": format(quantity, "f"),
                "source_reference_date": row["source_reference_date"],
                "source_id": row["source_id"],
            }
        )
        senders.append(
            {
                "sender_id": row["observation_id"],
                "eligible_surplus_kg": format(quantity, "f"),
                "quantity_unit": "kg",
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "evidence_type": "SCENARIO",
                "surplus_evidence": (
                    "SCENARIO: use the standardized reported expected monthly food-waste "
                    "quantity as available supply; assume all of it is edible, unserved, "
                    "redistributable, and applicable to November 2026. These conditions "
                    "are not verified."
                ),
                "source_id": row["source_id"],
                "business_name_en_romanized": name_en,
                "business_name_original_ko": row["business_name"],
                "address_en_romanized": address_en,
                "address_original_ko": address,
            }
        )

    capacity = total_supply / Decimal(len(receiver_rows))
    translated_receivers = []
    receivers = []
    for row in receiver_rows:
        name_en = english_name(row["organization_name"], organization=True)
        address_en = english_location(row["address_as_listed"])
        area_en = english_location(row["administrative_area"])
        translated_receivers.append(
            {
                "receiver_id": row["site_id"],
                "organization_name_en": name_en,
                "organization_name_original_ko": row["organization_name"],
                "administrative_area_en": area_en,
                "address_en_romanized": address_en,
                "address_original_ko": row["address_as_listed"],
                "capacity_kg_per_month_scenario": format(capacity, "f"),
                "source_id": row["source_id"],
            }
        )
        receivers.append(
            {
                "receiver_id": row["site_id"],
                "effective_receiving_capacity_kg": format(capacity, "f"),
                "capacity_unit": "kg",
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "evidence_type": "SCENARIO",
                "capacity_evidence": (
                    f"SCENARIO: equal-share capacity assumed as total scenario supply "
                    f"({format(total_supply, 'f')} kg/month) divided by "
                    f"{len(receiver_rows)} listed Seoul food-bank sites. No site capacity "
                    "or demand is published or verified."
                ),
                "source_id": SCENARIO_SOURCE,
                "organization_name_en": name_en,
                "organization_name_original_ko": row["organization_name"],
                "administrative_area_en": area_en,
                "address_en_romanized": address_en,
                "address_original_ko": row["address_as_listed"],
            }
        )

    pair_evidence = (
        "SCENARIO: assume every Seoul restaurant can give food to every listed Seoul "
        "food-bank site, with pickup within two hours after restaurant closing. Actual "
        "closing hours, acceptance, food compatibility, routes, and operations are not verified."
    )
    pairs = [
        {
            "sender_id": sender["sender_id"],
            "receiver_id": receiver["receiver_id"],
            "eligible": "true",
            "road_distance_km": "",
            "eligibility_evidence": pair_evidence,
            "source_id": SCENARIO_SOURCE,
        }
        for sender in senders
        for receiver in receivers
    ]

    write_csv(
        PROCESSED / "korea_seoul_restaurant_waste_observations_en.csv",
        translated_restaurants,
    )
    write_csv(PROCESSED / "korea_foodbank_sites_en.csv", translated_receivers)
    write_csv(SCENARIO / "senders.csv", senders)
    write_csv(SCENARIO / "receivers.csv", receivers)
    write_csv(SCENARIO / "eligibility_matrix.csv", pairs)

    print(f"Seoul restaurant sender nodes: {len(senders)}")
    print(f"Seoul food-bank receiver nodes: {len(receivers)}")
    print(f"All-eligible pair rows: {len(pairs)}")
    print(f"Total scenario supply: {format(total_supply, 'f')} kg/month")
    print(f"Per-site scenario capacity: {format(capacity, 'f')} kg/month")
    print(f"Saved scenario inputs under {SCENARIO}")


if __name__ == "__main__":
    main()

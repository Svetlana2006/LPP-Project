"""Extract OSM restaurant hours near the Seoul sender list and require strict matches."""

from __future__ import annotations

import argparse
import csv
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

try:
    import osmium
except ImportError:
    osmium = None

ROOT = Path(__file__).resolve().parents[1]
SENDER_FILE = ROOT / "data/scenario_refined/sender_observations.csv"
LOCATION_FILE = ROOT / "data/processed/seoul_osm_routed_locations.csv"
OUTPUT_FILE = ROOT / "data/scenario_refined/seoul_osm_restaurant_hours.csv"
OSM_VERSION = "south-korea-261116"
SNAPSHOT_DATE = "2026-11-17"
OSM_LICENSE = "OpenStreetMap contributors, ODbL 1.0"
AMENITIES = {"restaurant", "fast_food", "cafe", "food_court", "ice_cream"}
EXACT_GEOCODE_QUALITY = "road_and_house_number_match_in_Seoul"
ROAD_ADDRESS = re.compile(
    r"([가-힣0-9]+(?:대로|로|길)(?:\s*\d+(?:길|로))?(?:의\d+)?)\s*"
    r"(\d+(?:-\d+)?)"
)
OUTPUT_FIELDS = [
    "sender_id",
    "business_name_original_ko",
    "address_original_ko",
    "osm_object_type",
    "osm_object_id",
    "osm_name",
    "osm_amenity",
    "osm_opening_hours",
    "osm_addr_street",
    "osm_addr_housenumber",
    "distance_m",
    "geocoding_match_quality",
    "source_match_status",
    "source_record_url",
    "source_dataset_version",
    "source_snapshot_date",
    "source_license",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(character for character in normalized if character.isalnum())


def road_address_parts(value: str) -> tuple[str, str]:
    match = ROAD_ADDRESS.search(unicodedata.normalize("NFKC", value or ""))
    return (normalize(match.group(1)), normalize(match.group(2))) if match else ("", "")


def classify_match(
    target: dict[str, Any],
    feature: dict[str, Any],
    distance_m: float,
    *,
    feature_target_count: int,
    conflicting_hours: bool,
) -> str:
    address_road, address_number = road_address_parts(target["address_original_ko"])
    osm_road = normalize(feature["street"])
    osm_number = normalize(feature["house_number"])
    address_agrees = bool(
        address_road
        and address_number
        and osm_road == address_road
        and osm_number == address_number
    )
    address_conflicts = bool(
        (address_road and osm_road and osm_road != address_road)
        or (address_number and osm_number and osm_number != address_number)
    )
    if feature_target_count > 1:
        return "ambiguous_multiple_targets"
    if conflicting_hours:
        return "ambiguous_conflicting_osm_hours"
    if address_conflicts:
        return "candidate_address_conflict"
    if (
        (target["quality"] == EXACT_GEOCODE_QUALITY or address_agrees)
        and distance_m <= 50
    ):
        return "matched_exact_name_and_location"
    return "candidate_requires_location_review"


def _meters_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_m = 6_371_000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_m * math.asin(math.sqrt(haversine))


_HandlerBase = osmium.SimpleHandler if osmium is not None else object


class HoursHandler(_HandlerBase):
    def __init__(self, bounds: tuple[float, float, float, float]) -> None:
        super().__init__()
        self.bounds = bounds
        self.features: list[dict[str, Any]] = []

    def _save(self, obj: Any, object_type: str, lat: float, lon: float) -> None:
        tags = obj.tags
        amenity = tags.get("amenity", "")
        name = tags.get("name:ko") or tags.get("name", "")
        hours = tags.get("opening_hours", "")
        if amenity not in AMENITIES or not name or not hours:
            return
        min_lat, min_lon, max_lat, max_lon = self.bounds
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            return
        self.features.append(
            {
                "type": object_type,
                "id": obj.id,
                "name": name,
                "amenity": amenity,
                "hours": hours,
                "street": tags.get("addr:street", ""),
                "house_number": tags.get("addr:housenumber", ""),
                "lat": lat,
                "lon": lon,
            }
        )

    def node(self, node: Any) -> None:
        if node.location.valid():
            self._save(node, "node", node.location.lat, node.location.lon)

    def way(self, way: Any) -> None:
        locations = [node.location for node in way.nodes if node.location.valid()]
        if locations:
            lat = sum(location.lat for location in locations) / len(locations)
            lon = sum(location.lon for location in locations) / len(locations)
            self._save(way, "way", lat, lon)


def _source_rows(
    pbf_path: Path,
    senders: list[dict[str, str]],
    locations: list[dict[str, str]],
) -> list[dict[str, str]]:
    if osmium is None:
        raise RuntimeError(
            "Install the project research dependencies with "
            "'.venv\\Scripts\\python.exe -m pip install -e .[research]'"
        )
    location_by_id = {row["node_id"]: row for row in locations}
    targets: list[dict[str, Any]] = []
    for sender in senders:
        location = location_by_id.get(sender["sender_id"], {})
        try:
            lat = float(location["geocoded_latitude"])
            lon = float(location["geocoded_longitude"])
        except (KeyError, ValueError):
            continue
        targets.append(
            {
                **sender,
                "lat": lat,
                "lon": lon,
                "quality": location.get("geocoding_match_quality", ""),
            }
        )
    if not targets:
        raise ValueError("No sender coordinates were available for the OSM match.")

    bounds = (
        min(row["lat"] for row in targets) - 0.003,
        min(row["lon"] for row in targets) - 0.003,
        max(row["lat"] for row in targets) + 0.003,
        max(row["lon"] for row in targets) + 0.003,
    )
    handler = HoursHandler(bounds)
    handler.apply_file(str(pbf_path), locations=True, idx="sparse_file_array")

    possible: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    for feature in handler.features:
        feature_name = normalize(feature["name"])
        if not feature_name:
            continue
        for target in targets:
            if normalize(target["business_name_original_ko"]) != feature_name:
                continue
            distance = _meters_between(
                target["lat"], target["lon"], feature["lat"], feature["lon"]
            )
            if distance <= 200:
                possible.append((target, feature, distance))

    feature_target_counts: dict[tuple[str, int], int] = {}
    target_feature_rows: dict[str, list[tuple[dict[str, Any], float]]] = {}
    for target, feature, distance in possible:
        object_key = (feature["type"], feature["id"])
        feature_target_counts[object_key] = feature_target_counts.get(object_key, 0) + 1
        target_feature_rows.setdefault(target["sender_id"], []).append((feature, distance))

    result: list[dict[str, str]] = []
    for target, feature, distance in possible:
        object_key = (feature["type"], feature["id"])
        target_candidates = target_feature_rows[target["sender_id"]]
        conflicting_hours = len({item[0]["hours"] for item in target_candidates}) > 1
        status = classify_match(
            target,
            feature,
            distance,
            feature_target_count=feature_target_counts[object_key],
            conflicting_hours=conflicting_hours,
        )

        result.append(
            {
                "sender_id": target["sender_id"],
                "business_name_original_ko": target["business_name_original_ko"],
                "address_original_ko": target["address_original_ko"],
                "osm_object_type": feature["type"],
                "osm_object_id": str(feature["id"]),
                "osm_name": feature["name"],
                "osm_amenity": feature["amenity"],
                "osm_opening_hours": feature["hours"],
                "osm_addr_street": feature["street"],
                "osm_addr_housenumber": feature["house_number"],
                "distance_m": f"{distance:.1f}",
                "geocoding_match_quality": target["quality"],
                "source_match_status": status,
                "source_record_url": (
                    f"https://www.openstreetmap.org/{feature['type']}/{feature['id']}"
                ),
                "source_dataset_version": OSM_VERSION,
                "source_snapshot_date": SNAPSHOT_DATE,
                "source_license": OSM_LICENSE,
            }
        )
    return result


def refresh_candidate_statuses(
    candidate_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Re-evaluate saved exact-name candidates without rescanning the full PBF."""
    feature_target_counts: dict[tuple[str, str], int] = {}
    target_hours: dict[str, set[str]] = {}
    for row in candidate_rows:
        object_key = (row["osm_object_type"], row["osm_object_id"])
        feature_target_counts[object_key] = feature_target_counts.get(object_key, 0) + 1
        target_hours.setdefault(row["sender_id"], set()).add(row["osm_opening_hours"])

    refreshed: list[dict[str, str]] = []
    for row in candidate_rows:
        target = {
            "sender_id": row["sender_id"],
            "address_original_ko": row["address_original_ko"],
            "quality": row["geocoding_match_quality"],
        }
        feature = {
            "type": row["osm_object_type"],
            "id": row["osm_object_id"],
            "hours": row["osm_opening_hours"],
            "street": row["osm_addr_street"],
            "house_number": row["osm_addr_housenumber"],
        }
        object_key = (feature["type"], feature["id"])
        distance = float(row["distance_m"])
        status = classify_match(
            target,
            feature,
            distance,
            feature_target_count=feature_target_counts[object_key],
            conflicting_hours=len(target_hours[row["sender_id"]]) > 1,
        )
        refreshed.append({**row, "source_match_status": status})
    return refreshed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", type=Path)
    parser.add_argument("--senders", type=Path, default=SENDER_FILE)
    parser.add_argument("--locations", type=Path, default=LOCATION_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument(
        "--refresh-candidates",
        action="store_true",
        help="Re-evaluate the existing candidate CSV without rescanning the PBF.",
    )
    args = parser.parse_args()

    if args.refresh_candidates:
        rows = refresh_candidate_statuses(_read_csv(args.output))
    else:
        if args.pbf is None:
            parser.error("--pbf is required unless --refresh-candidates is used.")
        rows = _source_rows(
            args.pbf, _read_csv(args.senders), _read_csv(args.locations)
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    matched_senders = {
        row["sender_id"]
        for row in rows
        if row["source_match_status"] == "matched_exact_name_and_location"
    }
    print(
        f"Wrote {len(rows)} exact-name OSM candidates; "
        f"{len(matched_senders)} sender records passed the strict location match."
    )


if __name__ == "__main__":
    main()

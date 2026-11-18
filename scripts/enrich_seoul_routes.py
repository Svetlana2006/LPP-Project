"""Geocode Seoul addresses locally with Photon and add OSRM driving distances."""

from __future__ import annotations

import csv
import json
import re
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "data" / "scenario"
GEOCODE_CACHE = ROOT / "data" / "processed" / "seoul_osm_geocoding.csv"
ROUTED_LOCATIONS = ROOT / "data" / "processed" / "seoul_osm_routed_locations.csv"
PAIR_MATRIX = SCENARIO / "eligibility_matrix.csv"
PHOTON_URL = "http://127.0.0.1:2322/api"
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving"
USER_AGENT = (
    "LPP-Project/0.1 "
    "(https://github.com/Svetlana2006/LPP-Project; research use)"
)
OSM_ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0"
SEOUL_BOUNDS = (126.70, 37.40, 127.25, 37.72)
ROUTING_INTERVAL_SECONDS = 1.0
GEOCODER_ID = "Local Photon 1.0.0; GraphHopper South Korea dump dated 2026-11-09"
SENDER_BATCH_SIZE = 50
ADDRESS_NUMBER = re.compile(r"(?<!\d)(\d+(?:-\d+)?)(?!\d)")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write an empty dataset: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False
        ) as stream:
            temporary_path = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        for attempt in range(5):
            try:
                temporary_path.replace(path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.2 * (2**attempt))
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def request_json(url: str, *, retries: int = 5) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == retries - 1:
                raise
            retry_after = exc.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = float(retry_after)
            elif retry_after:
                retry_time = parsedate_to_datetime(retry_after)
                delay = max(
                    0.0,
                    (retry_time - datetime.now(timezone.utc)).total_seconds(),
                )
            else:
                delay = 60.0 if exc.code == 429 else 2**attempt
            print(
                f"HTTP {exc.code} from {urlparse(url).hostname}; retrying after "
                f"{delay:.0f} seconds.",
                flush=True,
            )
            time.sleep(delay)
        except URLError:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(f"Request failed after {retries} attempts: {url}")


def in_seoul(longitude: float, latitude: float) -> bool:
    west, south, east, north = SEOUL_BOUNDS
    return west <= longitude <= east and south <= latitude <= north


def candidate_rank(address_query: str, candidate: dict[str, Any]) -> int:
    properties = candidate.get("properties", {})
    road = properties.get("street", "")
    house_number = properties.get("housenumber", "")
    expected_road = re.search(
        r"([\uac00-\ud7a3\d]+(?:대로|로|길))",
        re.sub(r"\s*\(.*$", "", address_query),
    )
    candidate_road = road or properties.get("name", "")
    expected_numbers = ADDRESS_NUMBER.findall(
        re.sub(r"\s*\(.*$", "", address_query)
    )
    score = 0
    if expected_road and expected_road.group(1) in candidate_road:
        score += 3
    elif road and road in address_query:
        score += 3
    if house_number and house_number in expected_numbers:
        score += 3
    location = " ".join(
        str(properties.get(key, ""))
        for key in ("city", "district", "state")
    )
    if "서울" in location or "Seoul" in location:
        score += 1
    return score


def geocode_queries(address_query: str) -> list[str]:
    cleaned = re.sub(r"\s*\(.*$", "", address_query)
    cleaned = re.sub(r"_+", " ", cleaned)
    cleaned = re.sub(r"\s+[Bb]?\d+\s*층.*$", "", cleaned).strip()
    queries = []
    district = re.search(r"[\uac00-\ud7a3]+구", cleaned)
    road_number = re.search(
        r"([\uac00-\ud7a3\d]+(?:대로|로|길))\s*(\d+(?:-\d+)?)",
        cleaned,
    )
    road_name = re.search(r"([\uac00-\ud7a3\d]+(?:대로|로|길))", cleaned)
    if road_number:
        queries.append(
            " ".join(
                part
                for part in (
                    "서울특별시",
                    district.group(0) if district else "",
                    road_number.group(1),
                    road_number.group(2),
                )
                if part
            )
        )
    queries.extend((cleaned, address_query))
    if road_name:
        queries.append(road_name.group(1))
    return list(dict.fromkeys(query for query in queries if query))


def geocode(address_query: str) -> dict[str, Any]:
    best_candidate: tuple[int, dict[str, Any]] | None = None
    query_used = ""
    for query in geocode_queries(address_query):
        params = urlencode(
            {
                "q": query,
                "bbox": ",".join(str(value) for value in SEOUL_BOUNDS),
                "lat": 37.5665,
                "lon": 126.9780,
                "zoom": 12,
                "location_bias_scale": 0.1,
                "limit": 5,
            }
        )
        results = request_json(f"{PHOTON_URL}?{params}")
        if not isinstance(results, dict) or not isinstance(
            results.get("features"), list
        ):
            raise RuntimeError(f"Local Photon returned an unexpected response: {results}")
        candidates = []
        for result in results["features"]:
            coordinates = result.get("geometry", {}).get("coordinates", [])
            if len(coordinates) < 2:
                continue
            longitude = float(coordinates[0])
            latitude = float(coordinates[1])
            if in_seoul(longitude, latitude):
                candidates.append((candidate_rank(address_query, result), result))
        if candidates:
            best_for_query = max(candidates, key=lambda item: item[0])
            if best_candidate is None or best_for_query[0] > best_candidate[0]:
                best_candidate = best_for_query
                query_used = query
            if best_for_query[0] >= 6:
                break
    if best_candidate is None:
        return {
            "address_original_ko": address_query,
            "query_used": "",
            "status": "NOT_FOUND_IN_SEOUL",
            "latitude": "",
            "longitude": "",
            "display_name": "",
            "osm_type": "",
            "osm_id": "",
            "match_quality": "",
            "matched_road": "",
            "matched_house_number": "",
            "geocoding_source": GEOCODER_ID,
            "attribution": OSM_ATTRIBUTION,
        }

    score, result = best_candidate
    properties = result.get("properties", {})
    if properties.get("type") == "street" and not properties.get("housenumber"):
        quality = "street_only_approximation"
    elif score >= 7:
        quality = "road_and_house_number_match_in_Seoul"
    elif score >= 3:
        quality = "partial_address_match_in_Seoul"
    else:
        quality = "approximate_Seoul_match"
    display_fields = (
        properties.get("name"),
        properties.get("housenumber"),
        properties.get("street"),
        properties.get("district"),
        properties.get("city"),
        properties.get("state"),
        properties.get("country"),
    )
    return {
        "address_original_ko": address_query,
        "query_used": query_used,
        "status": "MATCHED",
        "latitude": result["geometry"]["coordinates"][1],
        "longitude": result["geometry"]["coordinates"][0],
        "display_name": ", ".join(
            dict.fromkeys(str(value) for value in display_fields if value)
        ),
        "osm_type": properties.get("osm_type", ""),
        "osm_id": properties.get("osm_id", ""),
        "match_quality": quality,
        "matched_road": properties.get("street", ""),
        "matched_house_number": properties.get("housenumber", ""),
        "geocoding_source": GEOCODER_ID,
        "attribution": OSM_ATTRIBUTION,
    }


def load_geocodes(addresses: list[str]) -> dict[str, dict[str, str]]:
    cached = {
        row["address_original_ko"]: row
        for row in read_csv(GEOCODE_CACHE)
        if row.get("geocoding_source") == GEOCODER_ID
    } if GEOCODE_CACHE.exists() else {}
    for index, address in enumerate(addresses, start=1):
        if cached.get(address, {}).get("status") == "MATCHED":
            continue
        row = geocode(address)
        cached[address] = row
        if index % 50 == 0 or index == len(addresses):
            write_csv_atomic(GEOCODE_CACHE, list(cached.values()))
            matched = sum(item["status"] == "MATCHED" for item in cached.values())
            print(
                f"Photon-geocoded address {index}/{len(addresses)}; "
                f"{matched}/{len(addresses)} matched.",
                flush=True,
            )
    write_csv_atomic(GEOCODE_CACHE, list(cached.values()))
    return cached


def fetch_table(
    senders: list[dict[str, str]],
    receivers: list[dict[str, str]],
    geocodes: dict[str, dict[str, str]],
    next_request_at: float,
) -> tuple[dict[str, Any], float]:
    if time.monotonic() < next_request_at:
        time.sleep(next_request_at - time.monotonic())
    points = [
        (geocodes[row["address_original_ko"]]["longitude"],
         geocodes[row["address_original_ko"]]["latitude"])
        for row in senders + receivers
    ]
    coordinates = ";".join(f"{longitude},{latitude}" for longitude, latitude in points)
    source_indexes = ";".join(str(index) for index in range(len(senders)))
    destination_indexes = ";".join(
        str(index) for index in range(len(senders), len(points))
    )
    query = urlencode(
        {
            "sources": source_indexes,
            "destinations": destination_indexes,
            "annotations": "distance",
        }
    )
    result = request_json(f"{OSRM_TABLE_URL}/{coordinates}?{query}")
    if result.get("code") != "Ok":
        raise RuntimeError(f"OSRM table request failed: {result}")
    return result, time.monotonic() + ROUTING_INTERVAL_SECONDS


def main() -> None:
    senders = read_csv(SCENARIO / "senders.csv")
    receivers = read_csv(SCENARIO / "receivers.csv")
    pairs = read_csv(PAIR_MATRIX)
    address_by_id = {
        row["sender_id"]: row["address_original_ko"] for row in senders
    }
    address_by_id.update(
        {row["receiver_id"]: row["address_original_ko"] for row in receivers}
    )
    addresses = list(dict.fromkeys(address_by_id.values()))
    geocodes = load_geocodes(addresses)
    unmatched = [
        address for address in addresses
        if geocodes.get(address, {}).get("status") != "MATCHED"
    ]
    if unmatched:
        raise RuntimeError(
            f"{len(unmatched)} address(es) did not match within Seoul. "
            f"Review {GEOCODE_CACHE}; no complete route matrix was written."
        )

    route_km: dict[tuple[str, str], str] = {}
    routed_locations: dict[str, dict[str, Any]] = {}
    next_request_at = time.monotonic()
    batch_count = (len(senders) + SENDER_BATCH_SIZE - 1) // SENDER_BATCH_SIZE
    for batch_number, start in enumerate(
        range(0, len(senders), SENDER_BATCH_SIZE), start=1
    ):
        sender_batch = senders[start : start + SENDER_BATCH_SIZE]
        result, next_request_at = fetch_table(
            sender_batch, receivers, geocodes, next_request_at
        )
        distances = result.get("distances", [])
        if len(distances) != len(sender_batch) or any(
            len(row) != len(receivers) for row in distances
        ):
            raise RuntimeError("OSRM returned an incomplete distance matrix.")
        for row_index, sender in enumerate(sender_batch):
            for column_index, receiver in enumerate(receivers):
                meters = distances[row_index][column_index]
                if meters is not None:
                    route_km[(sender["sender_id"], receiver["receiver_id"])] = (
                        f"{float(meters) / 1000:.3f}"
                    )

        for side, records in (("sources", sender_batch), ("destinations", receivers)):
            waypoints = result.get(side, [])
            if len(waypoints) != len(records):
                raise RuntimeError(f"OSRM returned incomplete {side} waypoints.")
            for record, waypoint in zip(records, waypoints):
                snap_lon, snap_lat = waypoint["location"]
                routed_locations[record["sender_id"] if side == "sources"
                                 else record["receiver_id"]] = {
                    "node_id": record["sender_id"] if side == "sources"
                    else record["receiver_id"],
                    "node_type": "sender" if side == "sources" else "receiver",
                    "address_original_ko": record["address_original_ko"],
                    "geocoded_latitude": geocodes[record["address_original_ko"]]["latitude"],
                    "geocoded_longitude": geocodes[record["address_original_ko"]]["longitude"],
                    "geocoding_source": geocodes[record["address_original_ko"]]["geocoding_source"],
                    "geocoding_match_quality": geocodes[record["address_original_ko"]]["match_quality"],
                    "osrm_snapped_latitude": snap_lat,
                    "osrm_snapped_longitude": snap_lon,
                    "osrm_snap_distance_m": waypoint.get("distance", ""),
                    "routing_profile": "driving",
                    "routing_source": "OSRM demo server using OpenStreetMap data",
                    "attribution": OSM_ATTRIBUTION,
                }
        print(
            f"Routed sender batch {batch_number}/{batch_count}.",
            flush=True,
        )

    missing_pairs = len(pairs) - len(route_km)
    if missing_pairs:
        raise RuntimeError(
            f"{missing_pairs} eligible pair(s) have no driving route in OSRM. "
            "The eligibility matrix was not modified."
        )

    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for pair in pairs:
        key = (pair["sender_id"], pair["receiver_id"])
        pair["road_distance_km"] = route_km[key]
        pair["road_distance_source"] = (
            "OSRM demo server, driving profile; OpenStreetMap road network"
        )
        pair["road_distance_retrieved_at_utc"] = retrieved_at

    write_csv_atomic(PAIR_MATRIX, pairs)
    write_csv_atomic(ROUTED_LOCATIONS, list(routed_locations.values()))
    qualities = {}
    for row in geocodes.values():
        qualities[row["match_quality"]] = qualities.get(row["match_quality"], 0) + 1
    snap_distances = [
        float(row["osrm_snap_distance_m"]) for row in routed_locations.values()
        if row["osrm_snap_distance_m"] != ""
    ]
    print(f"Completed {len(route_km)} driving distances.")
    print(f"Geocoding quality counts: {qualities}")
    print(
        "OSRM snap distance (m), maximum: "
        f"{max(snap_distances) if snap_distances else 'unavailable'}"
    )
    print(f"Distance retrieval timestamp (UTC): {retrieved_at}")
    print(f"Updated {PAIR_MATRIX}")
    print(f"Wrote {ROUTED_LOCATIONS}")


if __name__ == "__main__":
    main()

"""Typed domain objects for a single-period food allocation instance."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Sender:
    sender_id: str
    supply_kg: float
    period_start: str
    period_end: str
    pickup_deadline: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    evidence_type: str = "SCENARIO"
    evidence: str = "Synthetic test input"
    source_id: str = "scenario"


@dataclass(frozen=True)
class Receiver:
    receiver_id: str
    capacity_kg: float
    period_start: str
    period_end: str
    latitude: float | None = None
    longitude: float | None = None
    evidence_type: str = "SCENARIO"
    evidence: str = "Synthetic test input"
    source_id: str = "scenario"


@dataclass(frozen=True)
class PairEligibility:
    sender_id: str
    receiver_id: str
    eligible: bool
    road_distance_km: float | None
    evidence: str = ""
    source_id: str = "scenario"


@dataclass(frozen=True)
class AllocationInstance:
    senders: tuple[Sender, ...]
    receivers: tuple[Receiver, ...]
    pairs: tuple[PairEligibility, ...]


@dataclass(frozen=True)
class AllocationResult:
    allocations_kg: dict[tuple[str, str], float]
    objective_kg: float
    status: str
    method: str


@dataclass(frozen=True)
class TwoStageAllocationResult:
    stage1: AllocationResult
    stage2: AllocationResult
    stage1_optimal_kg: float
    stage2_total_kg_km: float
    stage2_average_km_per_kg: float | None

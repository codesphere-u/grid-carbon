"""Carbon-aware & tariff-aware compute workload scheduler (contiguous & interruptible windows)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GridSlot:
    """One hourly grid forecast slot with marginal carbon intensity and energy price."""

    slot_index: int
    label: str
    gco2_per_kwh: float
    price_usd_per_kwh: float


@dataclass(frozen=True)
class ComputeJob:
    job_id: str
    power_kw: float
    duration_hours: int
    earliest_slot: int
    deadline_slot: int  # Exclusive upper bound (must finish <= deadline_slot)
    interruptible: bool = False


@dataclass(frozen=True)
class JobSchedulePlan:
    job_id: str
    selected_slots: tuple[int, ...]
    energy_kwh: float
    scheduled_gco2: float
    baseline_immediate_gco2: float
    gco2_saved: float
    carbon_reduction_pct: float
    scheduled_cost_usd: float
    baseline_cost_usd: float
    cost_saved_usd: float


def schedule_job(
    job: ComputeJob,
    forecast: list[GridSlot],
    *,
    carbon_weight: float = 0.7,
    cost_weight: float = 0.3,
) -> JobSchedulePlan:
    """Choose the lowest-carbon/cost window meeting job SLA constraints before `deadline_slot`."""
    if job.duration_hours < 1 or job.power_kw <= 0:
        raise ValueError("duration_hours must be >= 1 and power_kw > 0")
    eligible = [s for s in forecast if job.earliest_slot <= s.slot_index < job.deadline_slot]
    eligible.sort(key=lambda s: s.slot_index)
    if len(eligible) < job.duration_hours:
        raise ValueError(
            f"Not enough forecast slots ({len(eligible)}) for {job.duration_hours}h job '{job.job_id}'"
        )

    max_c = max(s.gco2_per_kwh for s in eligible) or 1.0
    max_p = max(s.price_usd_per_kwh for s in eligible) or 1.0

    def _slot_score(slot: GridSlot) -> float:
        return carbon_weight * (slot.gco2_per_kwh / max_c) + cost_weight * (slot.price_usd_per_kwh / max_p)

    # Baseline: run immediately at earliest_slot..earliest_slot+duration
    baseline_slots = eligible[: job.duration_hours]

    if job.interruptible:
        chosen = sorted(eligible, key=lambda s: (_slot_score(s), s.slot_index))[: job.duration_hours]
        chosen.sort(key=lambda s: s.slot_index)
    else:
        best_window = baseline_slots
        best_score = sum(_slot_score(s) for s in baseline_slots)
        for i in range(1, len(eligible) - job.duration_hours + 1):
            win = eligible[i : i + job.duration_hours]
            # Verify contiguous hourly slots
            if win[-1].slot_index - win[0].slot_index != job.duration_hours - 1:
                continue
            sc = sum(_slot_score(s) for s in win)
            if sc < best_score:
                best_score = sc
                best_window = win
        chosen = best_window

    energy_kwh = job.power_kw * job.duration_hours
    sched_co2 = sum(s.gco2_per_kwh * job.power_kw for s in chosen)
    base_co2 = sum(s.gco2_per_kwh * job.power_kw for s in baseline_slots)
    sched_cost = sum(s.price_usd_per_kwh * job.power_kw for s in chosen)
    base_cost = sum(s.price_usd_per_kwh * job.power_kw for s in baseline_slots)

    saved_co2 = max(0.0, base_co2 - sched_co2)
    red_pct = (saved_co2 / base_co2 * 100.0) if base_co2 > 0 else 0.0
    return JobSchedulePlan(
        job_id=job.job_id,
        selected_slots=tuple(s.slot_index for s in chosen),
        energy_kwh=round(energy_kwh, 3),
        scheduled_gco2=round(sched_co2, 2),
        baseline_immediate_gco2=round(base_co2, 2),
        gco2_saved=round(saved_co2, 2),
        carbon_reduction_pct=round(red_pct, 2),
        scheduled_cost_usd=round(sched_cost, 4),
        baseline_cost_usd=round(base_cost, 4),
        cost_saved_usd=round(max(0.0, base_cost - sched_cost), 4),
    )

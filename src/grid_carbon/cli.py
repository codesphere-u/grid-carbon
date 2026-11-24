"""CLI for grid-carbon."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from grid_carbon.scheduler import ComputeJob, GridSlot, schedule_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grid-carbon",
        description="Carbon-aware & solar-peak batch workload scheduler.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Schedule a 4-hour ML training job into peak solar low-carbon hours")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        # Coal/gas evening peak (480 gCO2/kWh) vs midday solar trough (95 gCO2/kWh)
        forecast = [
            GridSlot(
                slot_index=h,
                label=f"{h:02d}:00",
                gco2_per_kwh=95.0 if 10 <= h <= 15 else 460.0 if h >= 18 or h <= 5 else 240.0,
                price_usd_per_kwh=0.08 if 10 <= h <= 15 else 0.24 if 18 <= h <= 21 else 0.14,
            )
            for h in range(24)
        ]
        plan = schedule_job(
            ComputeJob("nightly-ml-train", power_kw=2.5, duration_hours=4, earliest_slot=0, deadline_slot=20),
            forecast,
        )
        print(
            json.dumps(
                {
                    "job_id": plan.job_id,
                    "selected_slots": list(plan.selected_slots),
                    "baseline_gco2": plan.baseline_immediate_gco2,
                    "scheduled_gco2": plan.scheduled_gco2,
                    "gco2_saved": plan.gco2_saved,
                    "carbon_reduction_pct": plan.carbon_reduction_pct,
                    "cost_saved_usd": plan.cost_saved_usd,
                },
                indent=2,
            )
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

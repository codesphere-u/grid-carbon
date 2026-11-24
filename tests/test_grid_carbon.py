"""Tests for grid-carbon contiguous & interruptible scheduling, gCO2eq savings & CLI."""

from __future__ import annotations

import json

import pytest

from grid_carbon import ComputeJob, GridSlot, schedule_job
from grid_carbon.cli import main as cli_main


def test_contiguous_and_interruptible_scheduling_cuts_carbon_and_cost() -> None:
    forecast = [
        GridSlot(0, "00:00", 500.0, 0.25),
        GridSlot(1, "01:00", 480.0, 0.25),
        GridSlot(2, "02:00", 80.0, 0.09),
        GridSlot(3, "03:00", 450.0, 0.22),
        GridSlot(4, "04:00", 90.0, 0.08),
        GridSlot(5, "05:00", 95.0, 0.08),
    ]
    contig = schedule_job(ComputeJob("etl", 2.0, 2, 0, 6, interruptible=False), forecast)
    assert contig.selected_slots == (4, 5)
    assert contig.carbon_reduction_pct > 75.0
    assert contig.cost_saved_usd > 0.0

    flex = schedule_job(ComputeJob("checkpointed-ml", 2.0, 2, 0, 6, interruptible=True), forecast)
    assert flex.selected_slots == (2, 4)
    assert flex.scheduled_gco2 < contig.scheduled_gco2


def test_cli_demo(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["demo"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["carbon_reduction_pct"] > 70.0
    assert out["selected_slots"] == [10, 11, 12, 13]

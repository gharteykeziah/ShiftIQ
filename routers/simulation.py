"""routers/simulation.py — /api/simulate/monte-carlo, /api/simulate/whatif."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from dependencies import get_current_user, limiter
from schemas import MonteCarloRequest, WhatIfRequest
from services import simulation_service

router = APIRouter(prefix="/api/simulate", tags=["simulation"])


@router.post("/monte-carlo")
@limiter.limit("10/minute")
def simulate_monte_carlo(
    request: Request, req: MonteCarloRequest, current_user: dict = Depends(get_current_user),
) -> dict:
    return simulation_service.run_monte_carlo_sim(current_user["id"], req.weeks, req.n)


@router.post("/whatif")
@limiter.limit("20/minute")
def simulate_what_if(
    request: Request, req: WhatIfRequest, current_user: dict = Depends(get_current_user),
) -> dict:
    return simulation_service.run_whatif_sim(current_user["id"], req.description, req.dollar_change, req.weeks)

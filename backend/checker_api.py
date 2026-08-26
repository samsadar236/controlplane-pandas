"""FastAPI router for the general checker (T2.1) and the policy layer.

Wire it into the app with a single line in main.py:

    from .checker_api import router as checker_router
    app.include_router(checker_router)

Endpoints:
    POST /api/check      run the checks over one AI output, get a tiered decision
    GET  /api/policies   list the available use-case policies and their configs
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from .checker import check_output
from .policy import available_policies, load_policy

router = APIRouter(prefix="/api", tags=["checker"])


class CheckRequest(BaseModel):
    output: str
    context: str = ""
    input: str = ""
    use_case: str = "customer_support"
    policy: dict | None = None


@router.post("/check")
def check(req: CheckRequest):
    return check_output(
        use_case=req.use_case,
        output=req.output,
        context=req.context,
        input=req.input,
        policy=req.policy,
    )


@router.get("/policies")
def policies():
    return {
        "available": available_policies(),
        "policies": {name: load_policy(name) for name in available_policies()},
    }

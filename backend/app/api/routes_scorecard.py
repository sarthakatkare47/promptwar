import json
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.errors import AppError

router = APIRouter(prefix="/api/scorecard", tags=["Scorecard"])


@router.get("")
async def get_scorecard():
    """Returns the Trust Scorecard results written by the benchmark runner."""
    results_path = Path(__file__).resolve().parent.parent.parent / "benchmark" / "results" / "latest.json"
    if not results_path.exists():
        return {
            "status": "not_run",
            "message": "No benchmark results found. Run: python -m benchmark.run --mode deterministic",
        }

    try:
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise AppError("INTERNAL_ERROR", f"Failed to read benchmark results: {e}", status_code=500)

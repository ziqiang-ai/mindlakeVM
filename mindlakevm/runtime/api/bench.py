from fastapi import APIRouter, HTTPException
from models import BenchRequest, BenchResponse
from bench.runner import run_bench

router = APIRouter()


@router.post("/bench", response_model=BenchResponse)
def bench(req: BenchRequest):
    try:
        return run_bench(req)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"评测失败: {e}")

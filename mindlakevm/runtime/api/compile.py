from fastapi import APIRouter, HTTPException
from models import CompileRequest, CompileResponse, ErrorResponse
from compiler.pipeline import compile_document
import store
import re

router = APIRouter()


@router.post("/compile", response_model=CompileResponse)
def compile_doc(req: CompileRequest):
    if not req.document_content and not req.document_id:
        raise HTTPException(status_code=400, detail="document_content 或 document_id 必须提供其中一个")

    try:
        ir, package = compile_document(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"编译失败: {e}")

    skill_id = package.skill_id

    # 检查缓存
    existing = store.get(skill_id)
    if existing and not req.force_recompile:
        cached_ir, cached_pkg = existing
        return CompileResponse(
            kernel_id=cached_ir.kernel_id,
            cache_hit=True,
            similarity=1.0,
            ir=cached_ir,
            artifacts=cached_pkg,
        )

    store.save(skill_id, ir, package)

    return CompileResponse(
        kernel_id=ir.kernel_id,
        cache_hit=False,
        similarity=0.0,
        ir=ir,
        artifacts=package,
    )

from fastapi import APIRouter, HTTPException
from models import CompileRequest, CompileResponse
from compiler.pipeline import (
    compile_document,
    compile_request_fingerprint,
    materialize_compile_request,
)
import store

router = APIRouter()


@router.post("/compile", response_model=CompileResponse)
def compile_doc(req: CompileRequest):
    if not req.document_content and not req.document_id:
        raise HTTPException(status_code=400, detail="document_content 或 document_id 必须提供其中一个")

    try:
        resolved_req = materialize_compile_request(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    fingerprint = compile_request_fingerprint(resolved_req)
    if not req.force_recompile:
        cached_skill_id = store.get_cached_skill_id(fingerprint)
        if cached_skill_id:
            existing = store.get(cached_skill_id)
            if existing:
                cached_ir, cached_pkg = existing
                return CompileResponse(
                    kernel_id=cached_ir.kernel_id,
                    cache_hit=True,
                    similarity=1.0,
                    ir=cached_ir,
                    artifacts=cached_pkg,
                )

    try:
        ir, package = compile_document(resolved_req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"编译失败: {e}")

    skill_id = package.skill_id
    store.save(skill_id, ir, package)
    store.save_compile_cache(fingerprint, skill_id)

    return CompileResponse(
        kernel_id=ir.kernel_id,
        cache_hit=False,
        similarity=0.0,
        ir=ir,
        artifacts=package,
    )

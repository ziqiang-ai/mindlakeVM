import contextlib
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from api.compile import router as compile_router
from api.skills import router as skills_router
from api.run import router as run_router
from api.bench import router as bench_router
from api.tools import router as tools_router

logger = logging.getLogger(__name__)

# ── 尝试加载 MCP Server（可选依赖） ─────────────────────────────────────────
_mcp_available = False
_mcp_server = None
try:
    from mcp_server import mcp as _mcp_server
    _mcp_available = True
except ImportError:
    logger.info("MCP SDK 未安装，跳过 /mcp 端点挂载。安装: pip install 'mcp>=1.26.0'")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    if _mcp_available and _mcp_server:
        async with _mcp_server.session_manager.run():
            yield
    else:
        yield


app = FastAPI(
    title="MindLakeOS Demo API",
    version="0.1",
    description="Doc2Skill 认知编译平台 REST API + MCP Server",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(compile_router)
app.include_router(skills_router)
app.include_router(run_router)
app.include_router(bench_router)
app.include_router(tools_router)

# ── 挂载 MCP Server 到 /mcp ─────────────────────────────────────────────────
if _mcp_available and _mcp_server:
    app.mount("/mcp", _mcp_server.streamable_http_app())
    logger.info("MCP Server 已挂载到 /mcp")


@app.get("/health")
def health():
    return {"status": "ok", "mcp_available": _mcp_available}

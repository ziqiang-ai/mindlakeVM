from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from api.compile import router as compile_router
from api.skills import router as skills_router
from api.run import router as run_router
from api.bench import router as bench_router

app = FastAPI(
    title="MindLakeOS Demo API",
    version="0.1",
    description="Doc2Skill 认知编译平台 REST API",
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


@app.get("/health")
def health():
    return {"status": "ok"}

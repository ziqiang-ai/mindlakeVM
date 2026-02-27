# MindLakeVM Runtime

MindLakeOS Demo 后端服务，基于 FastAPI + OpenAI。

## 快速启动

```bash
cd mindlakevm/runtime

# 1. 安装依赖（使用 uv）
uv sync

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY

# 3. 启动服务
uv run uvicorn main:app --reload --port 8000
```

服务启动后访问 http://localhost:8000/docs 查看交互式 API 文档。

## 目录结构

```
runtime/
├── main.py               # FastAPI 入口
├── models.py             # Pydantic 数据模型（对齐 ir_schema_v0.3.json）
├── store.py              # 内存 Skill Store
├── api/
│   ├── compile.py        # POST /compile
│   ├── skills.py         # GET /skills, GET /skills/{id}
│   ├── run.py            # POST /run
│   └── bench.py          # POST /bench
├── compiler/
│   ├── pipeline.py       # 7阶段编译管线
│   └── llm.py            # LLM 调用封装
└── executor/
│   ├── runner.py         # Skill 执行器
│   ├── guardrail.py      # E核硬约束检查
│   ├── verifier.py       # V1/V2/V3 验证器
│   └── tracer.py         # T核执行 trace
└── bench/
    ├── runner.py         # Bench 评测入口
    ├── baselines.py      # Vanilla / RAG / MindLakeOS baseline
    ├── judges.py         # Judge 实现
    └── scenario_loader.py # 加载 specs/bench/scenarios/*.yaml
```

## 端点速览

| 端点 | 说明 |
|------|------|
| `POST /compile` | 编译文档 → SemanticKernelIR + Skill 包 |
| `GET /skills` | 列出所有已编译 Skill |
| `GET /skills/{id}` | 获取单个 Skill 详情 |
| `POST /run` | 挂载 Skill 执行用户输入（含 guardrail 拦截） |
| `POST /bench` | 运行 Vanilla/RAG/MindLakeOS 对比评测 |
| `GET /health` | 健康检查 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|-------|
| `OPENAI_API_KEY` | OpenAI API Key | 必填 |
| `OPENAI_MODEL` | 使用的模型 | `gpt-4o` |
| `SKILLS_DIR` | Skill 存储目录 | `./skills` |

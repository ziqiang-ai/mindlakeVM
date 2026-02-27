<p align="center">
  <h1 align="center">MindLakeVM</h1>
  <p align="center"><strong>Doc2Skill 认知编译平台 — 把企业文档编译成可执行、可验证、可追溯的 AI Skill</strong></p>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> •
  <a href="#核心能力">核心能力</a> •
  <a href="#架构概览">架构概览</a> •
  <a href="#api-参考">API 参考</a> •
  <a href="#bench-评测">Bench 评测</a> •
  <a href="#许可证">许可证</a>
</p>

---

## 问题：企业知识"可读但不可执行"

企业知识大量沉淀在 SOP、政策文件、RFC、Wiki 中，但面对 AI 场景存在四大痛点：

| 痛点 | 表现 |
|------|------|
| **执行不稳定** | 同一问题换个说法，AI 输出结果漂移 |
| **合规不可控** | 红线条款、审批条件容易被遗漏 |
| **上下文浪费** | 大量 token 用于复述文档而非推理 |
| **不可资产化** | 提示词和经验无法沉淀为可复用的组织资产 |

**MindLakeVM 的答案**：用认知编译器将"固态文档"编译成"液态 Skill"——可挂载、可验证、可执行的认知协议资产。

---

## 核心能力

### RNET 四核架构

MindLakeVM 基于 **RNET（Representation / Registration / Entropy / Transformation）** 四核语义指令集，将文档知识编译为结构化的中间表示（SemanticKernel IR），而非简单的提示词拼接。

| 核 | 职责 | 工程落点 |
|----|------|----------|
| **R — 表示** | 将任务从自然语言锚定为语义坐标 | `domain` / `object_type` / `semantic_space` |
| **N — 注册** | 将长文档拆分为可检索、可复用的资产目录 | `structure` / `schema` / `references[]` |
| **E — 熵控** | 用可执行门禁把不确定性收敛为工程可控 | `hard_constraints` / `soft_constraints` / `meta_ignorance` |
| **T — 转换** | 将执行过程显式化为可追溯路径与决策点 | `path[]` / `cot_steps` / `decision_points` |

### 三大核心流程

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Compile    │ ───→ │     Run      │ ───→ │    Bench     │
│  固态 → IR   │      │ 挂载 → 执行   │      │ 对比 → 验证   │
│  → Skill 包  │      │ → 门禁拦截    │      │ → 指标量化    │
└──────────────┘      └──────────────┘      └──────────────┘
```

- **Compile** — 输入企业文档，一键编译生成 RNET IR 与 Skill 目录（SKILL.md + references/）
- **Run** — 挂载 Skill 执行用户问题，支持红线拦截、引用追溯、执行 trace
- **Bench** — Vanilla vs RAG vs MindLakeVM 三组对比，量化 token 成本、成功率、门禁准确率

---

## 架构概览

```
mindlakeVM/
├── mindlakevm/
│   ├── runtime/                  # 后端服务（Python / FastAPI）
│   │   ├── main.py               #   FastAPI 入口
│   │   ├── models.py             #   Pydantic 数据模型（对齐 IR Schema v0.3）
│   │   ├── compiler/             #   7 阶段编译管线
│   │   │   ├── pipeline.py       #     Ingest → Classify → Extract → Synthesize → Package → Validate
│   │   │   └── llm.py            #     LLM 调用封装
│   │   ├── executor/             #   运行时执行引擎
│   │   │   ├── runner.py         #     Skill 执行器
│   │   │   ├── guardrail.py      #     E 核硬约束检查（红线拦截）
│   │   │   ├── verifier.py       #     V1 Schema / V2 引用 / V3 停止规则
│   │   │   └── tracer.py         #     T 核执行 trace
│   │   ├── bench/                #   评测引擎
│   │   │   ├── runner.py         #     Bench 评测入口
│   │   │   ├── baselines.py      #     三组 baseline 实现
│   │   │   ├── judges.py         #     Judge 评分器
│   │   │   └── scenario_loader.py
│   │   └── api/                  #   REST API 路由
│   │       ├── compile.py        #     POST /compile
│   │       ├── run.py            #     POST /run
│   │       ├── skills.py         #     GET  /skills
│   │       └── bench.py          #     POST /bench
│   └── ui/                       # 前端（React + TypeScript + TailwindCSS）
│       └── src/
│           ├── pages/            #   Compile / Run / Bench 三页
│           └── components/       #   RNETPanel 四核可视化组件
├── specs/                        # 工程规范库（单一真源）
│   ├── rnet/                     #   RNET 字段定义 + IR JSON Schema
│   ├── api/                      #   OpenAPI 合同 + 请求/响应示例
│   ├── bench/                    #   评测场景 YAML + Judge 规范
│   └── product/                  #   PRD / 线框 / 仓库结构
├── docs/                         # 理论文献（认知编译范式论文）
└── design/                       # 产品设计文档
```

### 技术栈

| 层 | 技术 |
|----|------|
| **后端** | Python 3.11+ · FastAPI · Pydantic v2 · OpenAI SDK |
| **前端** | React 19 · TypeScript · TailwindCSS 4 · Vite · Lucide Icons |
| **LLM** | OpenAI GPT-4o（默认）/ 任何 OpenAI 兼容 API（如 OpenRouter） |
| **规范** | JSON Schema · OpenAPI 3.0 · YAML Scenario Spec |

---

## 快速开始

### 前置条件

- Python 3.11+（推荐使用 [uv](https://github.com/astral-sh/uv) 管理）
- Node.js 18+
- OpenAI API Key（或兼容的 API 提供商）

### 1. 启动后端

```bash
cd mindlakevm/runtime

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY

# 启动服务
uv run uvicorn main:app --reload --port 8000
```

服务启动后访问 **http://localhost:8000/docs** 查看交互式 API 文档（Swagger UI）。

### 2. 启动前端

```bash
cd mindlakevm/ui

npm install
npm run dev
```

访问 **http://localhost:5173** 使用 Web UI。

### 3. 快速体验

```bash
# 编译一份 SOP 文档
curl -X POST http://localhost:8000/compile \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "SEV1 线上事故应急响应 SOP",
    "strategy": "default"
  }'

# 挂载 Skill 并执行
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "ops-sev1-incident-response",
    "user_input": "数据库主从延迟告警，需要在高峰期进行扩容操作"
  }'
```

---

## API 参考

| 端点 | 方法 | 说明 |
|------|------|------|
| `/compile` | POST | 编译文档 → SemanticKernel IR + Skill 包 |
| `/skills` | GET | 列出所有已编译 Skill |
| `/skills/{id}` | GET | 获取单个 Skill 详情（含完整 IR） |
| `/run` | POST | 挂载 Skill 执行用户输入（含门禁拦截 + trace + 引用） |
| `/bench` | POST | 运行 Vanilla / RAG / MindLakeVM 三组对比评测 |
| `/health` | GET | 健康检查 |

完整接口定义见 `specs/api/openapi_v0.1.yaml`。

### 关键数据结构

**SemanticKernel IR**（编译输出）：
```jsonc
{
  "kernel_id": "ops-sev1-incident-response-v1",
  "version": "0.3",
  "r": { "domain": "ops.incident", "object_type": "sop", "semantic_space": "..." },
  "n": { "structure": "step_by_step", "constraints": [...], "references": [...] },
  "e": { "hard_constraints": ["高峰期禁止扩缩容，除非 CTO 书面授权"], ... },
  "t": { "path": [{ "id": "step-1", "name": "...", "decision_points": [...] }], ... }
}
```

**RunResponse**（执行结果）：
```jsonc
{
  "output_text": "...",
  "blocked": true,                    // 是否被门禁拦截
  "violations": [{ "constraint": "...", "reason": "...", "severity": "hard" }],
  "trace": [{ "step_id": "step-1", "status": "completed", ... }],
  "evidence": [{ "source_path": "references/...", "excerpt": "..." }],
  "validation": { "passed": false, "schema_valid": true, "evidence_sufficient": true }
}
```

---

## Bench 评测

MindLakeVM 内置可复现的对比评测框架，证明"认知编译"相对于 Vanilla Prompt 和 RAG 的量化收益。

### 评测指标

| 指标 | 说明 |
|------|------|
| **Token Cost** | 输入/输出/总 token 消耗 |
| **Success Rate** | 任务完成正确率 |
| **Citation Rate** | 输出中包含证据引用的比例 |
| **Guardrail Block Rate** | 红线场景的拦截准确率 |

### 内置评测场景

| 场景 | 类型 | 核心验证点 |
|------|------|-----------|
| SOP 高峰期扩容门禁 | sop | 红线拦截 + 授权要求 |
| 政策报销审批矩阵 | policy | 条款引用 + 例外分支 |
| RFC API 网关设计 | rfc | JSON Schema 合规输出 |

### 预期对比结果

| | Vanilla | RAG | MindLakeVM |
|--|---------|-----|------------|
| **成功率** | ~20% | ~45% | **~90%** |
| **门禁准确率** | ~15% | ~40% | **~95%** |
| **Token 节省** | baseline | -10% | **-56%** |

```bash
# 运行评测
curl -X POST http://localhost:8000/bench \
  -H "Content-Type: application/json" \
  -d '{"scenario_id": "sop-scale-guardrail", "baselines": ["vanilla", "rag", "mindlakevm"]}'
```

---

## 理论基础

MindLakeVM 的设计基于**认知编译理论（Cognitive Compilation Theory）**，核心思想是将 AI Agent 的认知过程视为一个编译问题：

- **固态知识**（文档）→ 通过**认知编译器** → **液态 Skill**（可执行协议）
- 基于 **PET 熵框架**（Prompt Entropy Triad）：将 AI 执行的不确定性分解为触发熵（H_act）、语义熵（H_sem）、实现熵（H_exe），并通过 RNET 四核分别治理
- 区别于传统 RAG 的"检索→拼接"范式，MindLakeVM 实现**编译→挂载→门禁执行**的完整闭环

详细理论参见 `docs/` 目录下的论文。

---

## 规范库

`specs/` 目录是 MindLakeVM 的工程规范单一真源（Single Source of Truth）：

| 规范 | 文件 | 用途 |
|------|------|------|
| **RNET IR Schema** | `specs/rnet/ir_schema_v0.3.json` | 编译输出的结构校验 |
| **OpenAPI 合同** | `specs/api/openapi_v0.1.yaml` | 前后端接口契约 |
| **Bench 场景规范** | `specs/bench/scenario_spec_v0.1.json` | 评测场景结构定义 |
| **Judge 规范** | `specs/bench/judge_spec_v0.1.md` | 评分算法与口径 |
| **UI 映射表** | `specs/rnet/mapping_ui_v0.1.md` | 页面字段 → RNET 映射 |

修改任何字段结构须先更新对应 Schema，再同步实现，并记录到 `specs/changelog/`。

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API Key | **必填** |
| `OPENAI_MODEL` | 使用的模型 | `gpt-4o` |
| `OPENAI_BASE_URL` | API 基础地址（兼容 OpenRouter 等） | OpenAI 默认 |
| `SKILLS_DIR` | Skill 持久化目录 | `./skills` |

---

## 路线图

- [x] RNET 四核 IR Schema v0.3
- [x] 7 阶段编译管线（Compiler Pipeline）
- [x] 运行时执行引擎 + Guardrail 门禁
- [x] V1/V2/V3 验证器（Schema / 引用 / 停止规则）
- [x] Web UI 三页（Compile / Run / Bench）
- [x] Bench 评测框架 + 内置场景
- [ ] 多文档联合编译
- [ ] Skill 版本管理与治理字段
- [ ] 跨 Skill 组合编排（并联 / 循环）
- [ ] 对抗测试 Judge
- [ ] Protocol VM 熵向量实时暴露

---

## 许可证

[Apache License 2.0](LICENSE)
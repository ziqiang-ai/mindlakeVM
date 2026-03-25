# Specs 变更记录

本文档记录 `specs/` 目录下所有规范文件的版本变更历史。

**规则**：
- 破坏性变更（breaking change）必须 bump 版本号
- 非破坏性变更（新增可选字段、文档补充）可在当前版本内更新
- 每次变更必须在本文件中追加记录

---

## 版本命名规范

| 规范文件 | 版本格式 | 当前版本 |
|---------|---------|---------|
| `rnet/ir_schema_v{N}.json` | `v0.x` | `v0.3` |
| `api/openapi_v{N}.yaml` | `v0.x` | `v0.1` |
| `bench/scenario_spec_v{N}.json` | `v0.x` | `v0.1` |
| `bench/judge_spec_v{N}.md` | `v0.x` | `v0.1` |
| `rnet/rnet_core_v{N}.md` | `v0.x` | `v0.3` |
| `rnet/mapping_ui_v{N}.md` | `v0.x` | `v0.1` |
| `rnet/mapping_metrics_v{N}.md` | `v0.x` | `v0.1` |
| `registration/registration_model_v{N}.md` | `v0.x` | `v0.1` |
| `product/demo_repo_structure_v{N}.md` | `v0.x` | `v0.1` |
| `product/wireframe_text_v{N}.md` | `v0.x` | `v0.1` |
| `product/prd_v{N}.md` | `v0.x` | `v0.1` |
| `bench/baselines_v{N}.md` | `v0.x` | `v0.1` |

---

## 破坏性变更定义

| 规范文件 | 何时算破坏性变更 |
|---------|--------------|
| `ir_schema` | 增删改 key / 语义变更（如 `e.hard_constraints` 改名） |
| `openapi` | 请求/响应字段变更、endpoint 行为变更、状态码变更 |
| `scenario_spec` | 新增 required 字段、更改 judge 类型语义 |
| `judge_spec` | 更改 judge 计算算法、fatal 默认值变更 |

---

## 变更历史

### 2026-03-25 — 新增 PR 代码审查案例（v0.1）

**作者**：mindlakeVM 项目组  
**类型**：新增示例（无破坏性变更）

#### 新增文件

| 文件 | 说明 |
|------|------|
| `api/examples/code_review_compile_request.json` | PR 代码审查案例编译请求 |
| `api/examples/code_review_tool_handle.json` | PR review 工具注册请求 |
| `api/examples/code_review_tool_binding.json` | PR review 工具绑定请求 |
| `api/examples/code_review_run_simulate_request.json` | simulate 模式审查草稿请求 |
| `api/examples/code_review_run_live_request.json` | live 模式发布审查结果请求 |

#### 说明

- 提供一个更贴近真实工程协作的外部工具接入案例：PR 代码审查
- 覆盖 compile、tool register、binding、simulate 审查草稿、live 发布结果的完整链路

### 2026-03-25 — 新增 Fake CLI-Anything 接入示例（v0.1）

**作者**：mindlakeVM 项目组  
**类型**：新增示例（无破坏性变更）

#### 新增文件

| 文件 | 说明 |
|------|------|
| `api/examples/fake_cli_anything_compile_request.json` | fake CLI-Anything 案例编译请求 |
| `api/examples/fake_cli_anything_tool_handle.json` | fake 工具注册请求 |
| `api/examples/fake_cli_anything_tool_binding.json` | fake 工具绑定请求 |
| `api/examples/fake_cli_anything_run_simulate_request.json` | simulate 模式执行请求 |
| `api/examples/fake_cli_anything_run_live_request.json` | live 模式执行请求 |

#### 说明

- 提供一条从 compile 到 tool register/bind，再到 simulate/live 的最小外部工具接入演示链路
- 配套仓库内 fake CLI 工具与 e2e 脚本，便于本地演示和回归验证

### 2026-03-25 — 新增 Registration 规范（v0.1）

**作者**：mindlakeVM 项目组  
**类型**：新增规范（无破坏性变更）

#### 新增文件

| 文件 | 说明 |
|------|------|
| `registration/registration_model_v0.1.md` | Skill / Tool / Process / Event / Budget 的统一注册模型 |
| `registration/registration_object_model_diagram_v0.1.md` | `models.py + registry.py` 对应的统一注册对象模型设计图 |

#### 说明

- 将“注册”从 Skill 存储扩展为统一对象进入系统秩序的规则
- 明确注册对象分层：定义对象 / 关系对象 / 运行对象 / 治理对象
- 为后续 `Process Registry / Event Registry / Budget Registry / Checkpoint Registry` 留出规范入口

### 2025-02-27 — 初始版本（v0.1 全套）

**作者**：mindlakeVM 项目组  
**类型**：初始创建（无破坏性变更）

#### 新增文件

| 文件 | 说明 |
|------|------|
| `rnet/rnet_core_v0.3.md` | RNET 四核定义、字段语义、工程映射 |
| `rnet/ir_schema_v0.3.json` | SemanticKernelIR JSON Schema（单一真源） |
| `rnet/mapping_ui_v0.1.md` | UI 字段 → RNET 映射表（路演必备） |
| `rnet/mapping_metrics_v0.1.md` | Bench 指标 → RNET 映射表 |
| `api/openapi_v0.1.yaml` | `/compile` `/skills` `/run` `/bench` 完整合同 |
| `api/examples/compile_request.json` | 编译请求示例（SOP 场景） |
| `api/examples/compile_response.json` | 编译响应示例（含完整 IR） |
| `api/examples/run_request.json` | 执行请求示例（触发红线场景） |
| `api/examples/run_response.json` | 执行响应示例（blocked=true） |
| `api/examples/bench_request.json` | 评测请求示例 |
| `api/examples/bench_response.json` | 评测响应示例（含摘要卡） |
| `bench/scenario_spec_v0.1.json` | Bench 场景 YAML 的 JSON Schema |
| `bench/judge_spec_v0.1.md` | Judge 语义、算法、fatal/weight 口径 |
| `bench/baselines_v0.1.md` | Vanilla/RAG/MindLakeOS baseline 定义 |
| `bench/scenarios/sop_scale_guardrail.yaml` | SOP 场景（高峰期扩容门禁，6 个测试用例） |
| `bench/scenarios/policy_reimbursement_json.yaml` | 政策场景（报销审批矩阵，6 个测试用例） |
| `bench/scenarios/rfc_schema_output.yaml` | RFC 场景（API 网关设计，6 个测试用例） |
| `product/demo_repo_structure_v0.1.md` | Demo 仓库结构（runtime/ui/examples/bench） |
| `product/wireframe_text_v0.1.md` | 前端三页线框规格 + 路演彩排脚本 |
| `product/prd_v0.1.md` | PRD 规范库副本（同步自 design/v1-prd.md） |

#### IR Schema v0.3 初始字段清单

**新增（相比概念稿）**：
- `n.references[].required`：boolean，控制 V2 引用校验是否强制
- `t.path[].requires_evidence`：boolean，步骤级别的引用要求
- `e.meta_ignorance`：盲点列表（MetaIgnoranceProbe 输出）
- `RunResult.usage`：token 使用统计
- `BenchRow.false_positive_rate`：误拦截率
- `TraceStep.decision_taken`：实际走的决策分支

#### Bench 场景覆盖

| 场景 | 类型 | 测试用例 | 覆盖指标 |
|------|------|---------|---------|
| `sop-scale-guardrail` | sop | 6 | guardrail_block_rate、evidence、trace |
| `policy-reimbursement-json` | policy | 6 | citation_rate、output_keywords、trace |
| `rfc-schema-output` | rfc | 6 | schema_valid、guardrail_block_rate、trace |

---

## 待办（下一版本候选）

- [ ] 新增 `rnet/ir_schema_v0.4.json`：考虑新增 `r.parent_domain`（用于多级命名空间）
- [ ] 新增 RFC 场景的完整 JSON Schema 示例（`n.schema` 字段填充）
- [ ] 新增政策场景的 references 文件内容（`APPROVAL_MATRIX.md` 等）
- [ ] `api/openapi_v0.1.yaml`：考虑新增 `GET /bench/scenarios` 端点（列出可用场景）
- [ ] `bench/scenarios/`：新增更多场景（故障复盘 / 代码审查 / 合规审计）

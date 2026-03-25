# MindLakeVM EA-SKT Backlog（可执行任务清单 v1）

## 1. 范围与目标

本清单将以下文档落为工程任务：

- `docs/mindlakevm_easkt_optimization_roadmap.md`
- `/Users/mindlake/Downloads/语义核理论_学术论文.docx`
- `/Users/mindlake/Downloads/语义核与分布距离.md`

目标：在不破坏现有 API 兼容性的前提下，完成“分叉点可控 + 分布偏差可测 + 评测可回归”的 v1 落地。


## 2. 执行顺序（强依赖）

1. Epic A：编译一致性与基础度量
2. Epic B：执行器关键决策点控制
3. Epic C：验证器升级（V4/V5）
4. Epic D：API/MCP 诊断出口
5. Epic E：Bench 指标与报告升级


## 3. Epic A：编译一致性与基础度量

## A-1 对齐 `COMPILE_IR_TOOL` 与 Schema 必填

- 优先级：`P0`
- 目标：修复 `e.hard_constraints` required 不一致
- 修改文件：
  - `mindlakevm/runtime/compiler/pipeline.py`
  - `mindlakevm/runtime/tests/test_claude_integration.py`
- 具体动作：
  - `COMPILE_IR_TOOL.function.parameters.properties.e.required` 增加 `hard_constraints`
  - 更新/新增测试，断言 required 含 `hard_constraints`
- 验收标准：
  - 编译层测试通过
  - `COMPILE_IR_TOOL` 与 `specs/rnet/ir_schema_v0.3.json` 在 E 核 required 上一致

## A-2 compile 后新增 JSON Schema 校验

- 优先级：`P0`
- 目标：在 compile 阶段前移结构校验
- 修改文件：
  - `mindlakevm/runtime/compiler/pipeline.py`
  - `mindlakevm/runtime/requirements.txt`（如需引入 `jsonschema`）
  - `mindlakevm/runtime/tests/test_claude_integration.py`
- 具体动作：
  - 在 `_extract_ir()` 返回前，基于 `specs/rnet/ir_schema_v0.3.json` 校验 raw IR
  - 校验失败返回明确错误信息（建议 `ValueError`）
- 验收标准：
  - 非法 IR 在 compile 阶段被拒绝
  - 现有合法 case 不回归

## A-3 新增 `quality_report`（最小版）

- 优先级：`P1`
- 目标：建立四核质量基础评分出口
- 修改文件：
  - `mindlakevm/runtime/models.py`
  - `mindlakevm/runtime/compiler/pipeline.py`
  - `mindlakevm/runtime/store.py`
  - `mindlakevm/runtime/api/skills.py`
  - `mindlakevm/runtime/tests/test_claude_integration.py`
- 具体动作：
  - 在 `SemanticKernelIR` 新增可选 `quality_report` 字段（先 optional）
  - 先输出最小字段：`r_score/n_score/e_score/t_score/fork_point_count`
- 验收标准：
  - 老数据可读（向后兼容）
  - `GET /skills/{id}` 可见 `quality_report`


## 4. Epic B：执行器关键决策点控制

## B-1 扩展 `DecisionPoint` 元信息（兼容）

- 优先级：`P1`
- 目标：让分叉点具备可控优先级与证据要求
- 修改文件：
  - `mindlakevm/runtime/models.py`
  - `specs/rnet/ir_schema_v0.3.json`（新增可选字段）
  - `mindlakevm/runtime/compiler/pipeline.py`（tool schema 同步）
  - `mindlakevm/runtime/tests/test_claude_integration.py`
- 新增字段（全部 optional）：
  - `entropy_level`: `low|mid|high`
  - `decision_criticality`: `p1|p2|p3`
  - `evidence_required_scopes`: `list[str]`
- 验收标准：
  - 不影响现有 IR 反序列化
  - 新字段可以在样例 IR 中成功透传

## B-2 Agent Runner 增加 `p1` 决策门禁

- 优先级：`P1`
- 目标：关键决策点必须记录决策且满足证据要求
- 修改文件：
  - `mindlakevm/runtime/executor/agent_runner.py`
  - `mindlakevm/runtime/tests/test_claude_integration.py`
- 具体动作：
  - 对 `p1` 决策点，未调用 `report_decision` 时禁止 `step_complete`
  - 若 `evidence_required_scopes` 非空，至少有一条匹配 scope 的 evidence
- 验收标准：
  - 正常路径可完成
  - 缺决策记录/缺证据时产生明确失败信息

## B-3 Simple Runner 证据置信度分级

- 优先级：`P2`
- 目标：改进启发式 evidence 的可解释性
- 修改文件：
  - `mindlakevm/runtime/models.py`（`EvidenceItem` 可选 `confidence`）
  - `mindlakevm/runtime/executor/runner.py`
  - `mindlakevm/runtime/tests/test_claude_integration.py`
- 验收标准：
  - evidence 输出包含 `confidence`
  - 原有字段兼容


## 5. Epic C：验证器升级（V4/V5）

## C-1 新增 V4 决策完备性校验

- 优先级：`P1`
- 目标：关键分叉点可追溯
- 修改文件：
  - `mindlakevm/runtime/executor/verifier.py`
  - `mindlakevm/runtime/models.py`（`ValidationResult` 新增字段）
  - `mindlakevm/runtime/tests/test_claude_integration.py`
- 检查项：
  - `p1` 决策点是否存在 `report_decision`
  - trace 中是否可见分支处理痕迹
- 验收标准：
  - 缺失时 `passed=false` 或产生 warning（按策略）

## C-2 新增 V5 输出熵代理校验（SCR/SCE）

- 优先级：`P2`
- 目标：把“收敛性”纳入验证层
- 修改文件：
  - `mindlakevm/runtime/executor/verifier.py`
  - `mindlakevm/runtime/models.py`
  - `mindlakevm/runtime/tests/test_claude_integration.py`
- 说明：
  - v1 可先占位字段，实际采样逻辑放 bench 层
- 验收标准：
  - `ValidationResult` 可输出 `scr`/`sce` 或对应 warning


## 6. Epic D：API/MCP 诊断出口

## D-1 新增 `/diagnose_prompt_entropy`

- 优先级：`P1`
- 目标：输出四核评分 + 分布偏差代理
- 修改文件：
  - `mindlakevm/runtime/api/`（新增 `diagnose.py`）
  - `mindlakevm/runtime/main.py`
  - `mindlakevm/runtime/models.py`（新增请求/响应模型）
  - `specs/api/openapi_v0.1.yaml`
  - `mindlakevm/runtime/tests/`（新增 API 测试）
- 输出建议字段：
  - `r_score/n_score/e_score/t_score`
  - `distance_proxy`: `r_tv_proxy/n_kl_proxy/e_js_proxy/t_w1_proxy`
  - `i_wasted_proxy`
  - `recommendations`
- 验收标准：
  - OpenAPI 文档同步
  - 返回稳定 JSON 结构

## D-2 MCP `summary` 扩展偏差摘要

- 优先级：`P2`
- 目标：对外资源包含四核偏差快照
- 修改文件：
  - `mindlakevm/runtime/mcp_server.py`
- 验收标准：
  - `skill://{id}/summary` 增加可选偏差字段
  - 旧客户端兼容


## 7. Epic E：Bench 指标与报告升级

## E-1 Bench 输出新增代理指标

- 优先级：`P1`
- 目标：从单一 success/block 指标升级为四核可解释指标
- 修改文件：
  - `mindlakevm/runtime/bench/judges.py`
  - `mindlakevm/runtime/bench/runner.py`
  - `mindlakevm/runtime/models.py`（BenchResponse 扩展）
  - `specs/bench/judge_spec_v0.1.md`（新增口径）
  - `specs/api/openapi_v0.1.yaml`
- 新增指标：
  - `fork_coverage`
  - `decision_evidence_precision`
  - `scr`
  - `sce`
  - `i_wasted_proxy`
  - `r/n/e/t distance proxies`
- 验收标准：
  - `/bench` 返回新增字段
  - 至少一个场景能展示差异

## E-2 增加偏差雷达图所需响应结构

- 优先级：`P2`
- 目标：支持 UI 可视化“哪里变好”
- 修改文件：
  - `mindlakevm/runtime/models.py`
  - `specs/rnet/mapping_ui_v0.1.md`
  - `mindlakevm/ui/src/api.ts`（如同步前端）
- 验收标准：
  - API 返回 `distance_proxy` 子对象
  - UI 可以直接消费


## 8. 每周交付建议

## Week 1

- A-1 + A-2
- 产出：compile 一致性修复 PR

## Week 2

- A-3 + B-1
- 产出：IR 扩展字段与质量报告 PR

## Week 3

- B-2 + C-1
- 产出：关键决策点闭环 PR

## Week 4

- D-1 + E-1（最小指标）
- 产出：诊断 API + bench 指标 PR


## 9. 回归测试清单（最小）

1. compile 非法 IR 被拒绝（schema fail）
2. compile 合法 IR 正常落盘读取
3. agent 模式下 p1 决策点缺 `report_decision` 被拦截
4. required scope evidence 缺失触发验证失败或 warning
5. `/diagnose_prompt_entropy` 返回结构稳定
6. `/bench` 返回新增指标字段且兼容旧字段


## 10. 非目标（v1 不做）

- token 级真实熵在线估计（需要模型 logits 接入）
- 严格 Wasserstein/JS 的在线精确估计（先用 proxy）
- 全模型族泛化结论（先在现有 Qwen 路线验证）

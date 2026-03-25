
# mindlakeVM Specs

本目录是 **mindlakeVM 的规范库（Specs Repository）**：用于定义 **RNET 语义核指令集**、**IR 数据结构**、**HTTP API 合同**、**Bench 评测口径** 与 **对外 Demo/产品规格**。  
目标：**规范先行、实现可替换、评测可复现、路演可自证（R/N/E/T 可验核）**。

---

## 0. 你应该从哪里开始？

- **要实现编译器/运行时/前端**：先看 `specs/api/openapi_v0.1.yaml` + `specs/rnet/ir_schema_v0.3.json`
- **要跑对比 Demo（vanilla vs RAG vs mindlakeVM）**：先看 `specs/bench/scenarios/` + `specs/bench/judge_spec_v0.1.md`
  * 项目案例链路示例：`docs/llmos_kernel_architecture_case.md` + `specs/api/examples/llmos_kernel_compile_request.json` + `specs/bench/scenarios/llmos_kernel_architecture.yaml`
  * 外部工具接入演示：`docs/fake_cli_anything_case.md` + `specs/api/examples/fake_cli_anything_*.json` + `mindlakevm/runtime/tests/test_e2e_fake_cli_anything_flow.sh`
  * 真实场景演示：`docs/code_review_case.md` + `specs/api/examples/code_review_*.json` + `mindlakevm/runtime/tests/test_e2e_code_review_flow.sh`
- **要对外讲清楚“不是玄学”**：先看 `specs/rnet/mapping_ui_v0.1.md`（页面字段→R/N/E/T）
- **要继续做 runtime / tool / process 治理**：先看 `specs/registration/registration_model_v0.1.md`
- **要改字段/加能力**：先看 `specs/changelog/specs_changelog.md`（版本与破坏性变更规则）

---

## 1. 目录结构总览（规范分层）

```text
specs/
  README.md                         # 本文件：规范索引入口
  registration/                     # 注册体系规范（“对象进入系统秩序的规则”）
    registration_model_v0.1.md      # Skill / Tool / Process / Event / Budget 的统一注册模型
    registration_object_model_diagram_v0.1.md # models.py + registry.py 对应设计图
  rnet/                             # R/N/E/T 本体与字段定义（“语言标准”）
    rnet_core_v0.3.md               # 四核定义、字段语义、工程映射
    ir_schema_v0.3.json             # SemanticKernelIR JSON Schema（单一真源）
    mapping_ui_v0.1.md              # UI字段→RNET映射表（路演必备）
    mapping_metrics_v0.1.md         # Bench指标→RNET映射表
  api/                              # HTTP API 合同（“接口标准”）
    openapi_v0.1.yaml               # /compile /skills /run /bench 合同
    examples/                       # API请求响应示例（前端/测试用）
      compile_request.json
      fake_cli_anything_compile_request.json
      fake_cli_anything_tool_handle.json
      fake_cli_anything_tool_binding.json
      fake_cli_anything_run_simulate_request.json
      fake_cli_anything_run_live_request.json
      code_review_compile_request.json
      code_review_tool_handle.json
      code_review_tool_binding.json
      code_review_run_simulate_request.json
      code_review_run_live_request.json
      llmos_kernel_compile_request.json
      llmos_kernel_run_questions.json
      compile_response.json
      run_request.json
      run_response.json
      bench_request.json
      bench_response.json
  bench/                            # 评测规范（“验收标准”）
    scenario_spec_v0.1.json          # Scenario YAML 的 JSON Schema（单一真源）
    judge_spec_v0.1.md               # Judges 语义、算法、fatal/weight 口径
    baselines_v0.1.md               # vanilla/rag/mindlakevm baseline 定义
    scenarios/                      # 可复现实验场景（/bench 直接读取）
      sop_scale_guardrail.yaml
      policy_reimbursement_json.yaml
      llmos_kernel_architecture.yaml
  product/                          # 对外演示材料（“产品标准”）
    demo_repo_structure_v0.1.md     # demo 仓库结构（examples/ui/bench/runtime）
    wireframe_text_v0.1.md          # 最小前端线框文字规格（页面+字段+RNET映射）
    prd_v0.1.md                     # 产品设计文档
  changelog/
    specs_changelog.md              # specs 变更记录（版本/破坏性变更）
```

---

## 2. 单一真源（Single Source of Truth）

mindlakeVM 的规范遵循“单一真源”原则：**实现必须对齐这些文件**。

1. **RNET IR Schema**

* `specs/rnet/ir_schema_v0.3.json`
  用途：校验编译输出的 `SemanticKernelIR`，并作为 API 结构定义的源头。

2. **HTTP API 合同**

* `specs/api/openapi_v0.1.yaml`
  用途：UI ↔ runtime 的契约；examples 用于 mock / e2e 测试。

3. **Bench ScenarioSpec**

* `specs/bench/scenario_spec_v0.1.json`
  用途：`bench/scenarios/*.yaml` 的结构校验；runtime 的 `/bench` 必须先校验再执行。

---

## 3. RNET（R/N/E/T）在 specs 中的落点

RNET 不是口号，而是贯穿 specs 的“可检验结构”。对应落点如下：

### 3.1 R（Representation）

* 位置：`specs/rnet/rnet_core_v0.3.md`
* 机器形态：`ir_schema_v0.3.json` 中的 `r.domain / r.object_type / r.semantic_space`
* UI 显示映射：`specs/rnet/mapping_ui_v0.1.md`

### 3.2 N（Registration）

* 机器形态：`n.structure / n.schema / n.constraints`
* 渐进披露与证据引用：Bench judges 与 scenarios 会直接验证 `references` 使用情况

  * 位置：`specs/bench/judge_spec_v0.1.md`

### 3.3 E（Entropy）

* 机器形态：`e.output_constraint / e.format / e.target_entropy / e.hard_constraints / e.soft_constraints`
* 门禁（blocked/violations）与格式闭环：由 runtime 执行并由 bench judges 验证

  * 位置：`specs/bench/judge_spec_v0.1.md`

### 3.4 T（Transformation）

* 机器形态：`t.path / t.cot_steps`
* 可追溯执行（trace steps coverage）：由 runtime 输出 trace，并由 bench judges 验证

  * 位置：`specs/bench/judge_spec_v0.1.md`

---

## 4. 如何用这些 specs 开发（实现指南）

### 4.1 runtime（后端）应做什么？

* **编译**：实现 `/compile`，输出必须通过 `ir_schema_v0.3.json` 校验
* **执行**：实现 `/run`，返回 `blocked/violations/evidence/trace/usage` 等字段（由 OpenAPI 定义）
* **评测**：实现 `/bench`

  * 读取 `bench/scenarios/*.yaml`
  * 用 `scenario_spec_v0.1.json` 校验
  * 执行 baselines（vanilla/rag/mindlakevm）
  * 跑 `judges` 计算分数、通过率与 breakdown

### 4.2 ui（前端）应做什么？

* 以 `openapi_v0.1.yaml` 为唯一接口契约
* 以 `specs/api/examples/*.json` 作为 mock 数据源
* 页面字段严格按 `specs/rnet/mapping_ui_v0.1.md` 展示（R/N/E/T 分组）

### 4.3 bench（评测）应做什么？

* 新增场景：只需要在 `specs/bench/scenarios/` 增加 YAML
* 新增 judge：先更新 `judge_spec_v0.1.md`（定义语义与算法），再在实现中注册

---

## 5. 版本与破坏性变更规则

### 5.1 版本命名（建议）

* RNET core：`v0.3`（与编译器 IR 版本同步）
* IR schema：`v0.3`
* OpenAPI：`v0.1`
* ScenarioSpec：`v0.1`
* JudgeSpec / Product docs：`v0.1`

### 5.2 何时算破坏性变更？

* **IR schema**：增删改 key / 语义变更（例如 `e.hard_constraints` 改名）→ bump `ir_schema` 版本
* **OpenAPI**：请求/响应字段变更或 endpoint 行为变更 → bump `openapi` 版本
* **ScenarioSpec**：新增 required 字段 / 更改 judge 类型语义 → bump `scenario_spec` 版本

所有变更必须同步记录在：

* `specs/changelog/specs_changelog.md`

---

## 6. 快速导航（常用文件）

* RNET 概念定义：`specs/rnet/rnet_core_v0.3.md`
* IR Schema（必对齐）：`specs/rnet/ir_schema_v0.3.json`
* API 合同（必对齐）：`specs/api/openapi_v0.1.yaml`
* Bench 场景规范：`specs/bench/scenario_spec_v0.1.json`
* Bench 判定口径：`specs/bench/judge_spec_v0.1.md`
* UI 字段→RNET：`specs/rnet/mapping_ui_v0.1.md`
* Demo 目录结构：`specs/product/demo_repo_structure_v0.1.md`
* 前端线框文字规格：`specs/product/wireframe_text_v0.1.md`
* PRD：`specs/product/prd_v0.1.md`

---

## 7. 贡献规范（新增/修改 specs 的建议流程）

1. 明确变更层级：RNET / API / Bench / Product
2. 先改“单一真源”（schema/openapi/spec），再改实现
3. 对 bench：新增或更新对应 `scenarios/*.yaml`，保证可复现
4. 更新 `specs/changelog/specs_changelog.md`
5. 若 UI 字段受影响，更新 `mapping_ui_v0.1.md`

---

## 8. 设计原则（mindlakeVM 的“去玄学”原则）

* **结构可校验**：IR / Scenario / API 都有 schema
* **过程可追溯**：运行时必须产出 trace 与 evidence
* **门禁可量化**：blocked/violations 在 bench 中可验证
* **映射可展示**：所有 UI 字段与指标都可回溯到 R/N/E/T

以上原则的最终目的：让观众/评委看到 mindlakeVM 的核心不是“提示技巧”，而是一套 **可验证的认知指令集 + 运行时门禁 + 可复现实验体系**。

```

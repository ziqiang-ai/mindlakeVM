# Session Brief — MindLakeVM 规范库构建

**文档目的**：记录本轮工作会话的内容、决策和产出，梳理项目全部文件的相互关联，为后续分析和工程实现提供快速上下文。

**日期**：2025-02-27  
**会话范围**：规范库（`specs/`）从零构建 + 跨目录联合分析

---

## 一、会话工作摘要

### 1.1 起点

用户提供了 `specs/README.md`（已存在，内容完整），要求按其定义的结构创建所有对应规范文件。

### 1.2 完成的工作

本轮会话共创建 **24 个文件**，覆盖规范库全部模块：

| 模块 | 文件数 | 完成状态 |
|------|-------|---------|
| `specs/rnet/` | 4 | ✅ 完成 |
| `specs/api/` | 7 | ✅ 完成 |
| `specs/bench/` | 6 | ✅ 完成 |
| `specs/product/` | 3 | ✅ 完成 |
| `specs/changelog/` | 1 | ✅ 完成 |
| 联合分析文档 | 2 | ✅ 完成 |

### 1.3 分析工作

完成了三轮跨目录联合分析：
1. **`docs/` × `specs/rnet/`**：理论层与工程规范层的对应关系
2. **`cps-research/`** 目录分析：研究工作坊素材梳理
3. 以上两份分析均已写成文档保存

---

## 二、项目全部文件关联图

### 2.1 目录层级与定位

```
mindlakeVM/
├── cps-research/          ① 研究工作坊（原始对话素材）
├── docs/                  ② 理论文献（提炼后的理论体系）
├── design/                ③ 产品设计（PRD 与设计决策）
└── specs/                 ④ 工程规范（可执行合同与标准）
    ├── rnet/                 语义基础层（单一真源）
    ├── api/                  接口合同层
    ├── bench/                评测标准层
    ├── product/              产品形态层
    └── changelog/            变更追踪层
```

**信息流方向**：
```
cps-research/ → docs/ → design/ → specs/rnet/ → specs/api/ → specs/bench/
（思想实验）  （理论）  （产品）  （语义核心）  （接口合同）  （验收标准）
```

---

### 2.2 核心文件关联图（详细）

```
┌─────────────────────────────────────────────────────────────────────┐
│  cps-research/（研究素材层）                                          │
│                                                                     │
│  cps-skill.md ──────────────────────────────→ 三类熵定义             │
│  _Doc2Skill 编译管线设计.md ─────────────────→ 7阶段编译管线          │
│  cps-metaprompt.md ──────────────────────────→ CP vs Meta-Prompt    │
│  Branch·认知编译与Agent设计-编译器.md ──────→ 认知编译范式           │
└─────────────────┬───────────────────────────────────────────────────┘
                  │ 提炼
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  docs/（理论文献层）                                                  │
│                                                                     │
│  cognitive_compilation_agent_paradigm.md ────→ 三态/五原则/L1-L4     │
│  cognitive_compilation_pet_unified.md ───────→ PET熵公式/统一框架    │
│  congintion-compilation.md ──────────────────→ 认知编译综合论述      │
│  认知熵编译理论.md ───────────────────────────→ 统一框架中文版        │
└─────────────────┬───────────────────────────────────────────────────┘
                  │ 落地
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  design/（产品设计层）                                                │
│                                                                     │
│  v1-prd.md ──────────────────────────────────→ 功能需求/API定义      │
└─────────────────┬───────────────────────────────────────────────────┘
                  │ 规范化
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  specs/（工程规范层）                                                 │
│                                                                     │
│  README.md ──────────→ 目录索引（所有规范文件的入口）                  │
│                                                                     │
│  rnet/（语义核，单一真源）                                            │
│  ├── rnet_core_v0.3.md ──────────────────────→ 字段语义定义          │
│  ├── ir_schema_v0.3.json ────────────────────→ 数据结构合同（SSoT）  │
│  ├── mapping_ui_v0.1.md ─────────────────────→ UI 组件绑定规则       │
│  └── mapping_metrics_v0.1.md ────────────────→ Bench 指标映射        │
│          │ $ref                                                      │
│          ▼                                                           │
│  api/（接口合同层）                                                   │
│  ├── openapi_v0.1.yaml ──────────────────────→ 5个端点的完整合同     │
│  └── examples/（6个JSON）─────────────────────→ 请求/响应示例        │
│          │ 场景驱动                                                   │
│          ▼                                                           │
│  bench/（评测标准层）                                                 │
│  ├── scenario_spec_v0.1.json ────────────────→ 场景 YAML 的 Schema  │
│  ├── judge_spec_v0.1.md ─────────────────────→ Judge 算法与口径      │
│  ├── baselines_v0.1.md ──────────────────────→ Baseline 实现规范     │
│  └── scenarios/（3个YAML）───────────────────→ 具体评测场景          │
│          │ 产品定义                                                   │
│          ▼                                                           │
│  product/（产品形态层）                                               │
│  ├── demo_repo_structure_v0.1.md ────────────→ 仓库结构定义          │
│  ├── wireframe_text_v0.1.md ─────────────────→ 前端线框+路演脚本     │
│  └── prd_v0.1.md ────────────────────────────→ PRD 规范库副本        │
│                                                                     │
│  changelog/                                                         │
│  └── specs_changelog.md ────────────────────→ 变更历史追踪           │
│                                                                     │
│  分析文档                                                            │
│  ├── docs_rnet_joint_analysis.md ────────────→ docs×rnet 联合分析    │
│  └── session_brief.md（本文）────────────────→ 会话摘要+文件关联图    │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 2.3 关键依赖关系（工程实现视角）

#### `ir_schema_v0.3.json` 是核心枢纽

所有其他规范文件都直接或间接依赖它：

```
ir_schema_v0.3.json
    ├── 被 openapi_v0.1.yaml 引用（$ref SemanticKernelIR / RunResult / BenchResult）
    ├── 被 rnet_core_v0.3.md 描述（字段语义的文字版）
    ├── 被 mapping_ui_v0.1.md 绑定（UI 元素→字段路径）
    ├── 被 mapping_metrics_v0.1.md 映射（Bench 指标→字段路径）
    ├── 被 judge_spec_v0.1.md 引用（RunResult 字段用于 judge 计算）
    └── 被 scenario_spec_v0.1.json 引用（expects 字段来自 RunResult）
```

**修改原则**：改字段结构必须先改 `ir_schema`，bump 版本，再更新上游所有引用文件，最后记录到 `changelog`。

#### `openapi_v0.1.yaml` 是接口枢纽

```
openapi_v0.1.yaml
    ├── examples/ → 具体 JSON 示例与 YAML 描述对应
    ├── → 前端 api/client.ts（wire format）
    ├── → runtime/api/*.py（后端路由实现）
    └── → bench/baselines/mindlakevm.py（调用 /run 端点）
```

#### `bench/scenarios/*.yaml` 是验收枢纽

```
scenarios/sop_scale_guardrail.yaml
scenarios/policy_reimbursement_json.yaml
scenarios/rfc_schema_output.yaml
    ├── 必须符合 scenario_spec_v0.1.json Schema
    ├── 引用 judge_spec_v0.1.md 中定义的 judge ID
    ├── 通过 openapi_v0.1.yaml 的 /bench 端点执行
    └── 对比 baselines_v0.1.md 定义的三组 baseline
```

---

### 2.4 RNET 四核与文件的对应

| RNET 核 | 理论来源 | 规范定义 | UI 展示 | Bench 指标 |
|--------|---------|---------|---------|-----------|
| **R**（语义坐标） | `docs/cognitive_compilation_agent_paradigm.md` §1 | `ir_schema#/RCore` | `mapping_ui: Compile页/Domain/ObjectType` | 路由准确率（非直接指标） |
| **N**（知识注册） | `docs/pet_unified.md` H_S 熵减 | `ir_schema#/NCore` + `ReferenceEntry` | `mapping_ui: EvidenceViewer` | `citation_rate` |
| **E**（熵控门禁） | `docs/pet_unified.md` H_Y 熵减 | `ir_schema#/ECore` | `mapping_ui: GuardrailPanel`（红色） | `guardrail_block_rate` / `false_positive_rate` |
| **T**（执行路径） | `cps-research/_Doc2Skill.md` CP Spec workflow | `ir_schema#/TCore` + `PathStep` | `mapping_ui: TraceTimeline` | `success_rate`（trace_coverage judge） |

---

## 三、核心理论在工程规范中的落点速查

### 3.1 来自 `cps-research/cps-skill.md`

| 研究概念 | 工程落点 | 文件 |
|---------|---------|------|
| 触发熵 $H_{\text{act}}$ | `r.semantic_space` + `r.object_type`（路由锚点） | `ir_schema_v0.3.json#/RCore` |
| 语义熵 $H_{\text{sem}}$ | `n.constraints` + `n.references[]` | `ir_schema_v0.3.json#/NCore` |
| 实现熵 $H_{\text{exe}}$ | `t.path[]` + `ValidationResult`（V1/V2/V3） | `ir_schema_v0.3.json#/TCore` |
| 渐进披露 | SKILL.md（指挥层）vs references/（查表层） | `demo_repo_structure_v0.1.md` |
| Q(Skill) 质量公式 | `BenchSummary.success_rate_delta`（代理） | `ir_schema_v0.3.json#/BenchSummary` |

### 3.2 来自 `cps-research/_Doc2Skill 编译管线设计.md`

| 编译管线阶段 | 工程落点 | 文件 |
|------------|---------|------|
| Phase 0 Ingest | `runtime/compiler/ingest.py` | `demo_repo_structure_v0.1.md` |
| Phase 1 Classify | `r.object_type`（文档类型识别结果） | `ir_schema_v0.3.json#/RCore` |
| Phase 2 Extract → CP Spec | `SemanticKernelIR`（编译器输出） | `ir_schema_v0.3.json` |
| Phase 3 Synthesize（渐进披露分层） | `SkillPackage.files_tree` + 各文件类型 | `ir_schema_v0.3.json#/SkillPackage` |
| Phase 4 Package（SKILL.md 规范） | `demo_repo_structure_v0.1.md` SKILL.md 格式 | `demo_repo_structure_v0.1.md` |
| Phase 5 Validate | `ValidationResult`（V1 schema） | `ir_schema_v0.3.json#/ValidationResult` |
| Phase 6 Test & Release | `bench/scenarios/*.yaml`（回归测试集） | `bench/scenarios/` |

### 3.3 来自 `cps-research/cps-metaprompt.md`

| 概念 | 工程落点 | 说明 |
|-----|---------|------|
| 认知协议（CP）= 规范层 | `SemanticKernelIR` 整体 | 可执行的"认知状态机" |
| 元提示（Meta-Prompt）= 编译层 | `runtime/compiler/` 管线 | 把 IR 渲染为实际 Prompt |
| CP → Meta-Prompt → Prompt Instance | compile → run 两步 API | `/compile` 生成 IR，`/run` 实例化执行 |

### 3.4 来自 `docs/` 理论文献

| 理论概念 | 工程落点 | 文件 |
|---------|---------|------|
| PET 熵三分量 H_I/H_S/H_Y | R/N/E 三核 | `ir_schema_v0.3.json` |
| 协议成熟度 L4 | MindLakeVM = L4（Bench 对比的理论依据） | `docs_rnet_joint_analysis.md` §2.5 |
| 五大设计原则 | RNET 字段设计逻辑 | `docs_rnet_joint_analysis.md` §2.6 |
| MetaIgnoranceProbe | `e.meta_ignorance[]` | `ir_schema_v0.3.json#/ECore` |

---

## 四、当前规范的空白与后续工作

### 4.1 已识别的规范空白（来自联合分析）

| 空白 | 优先级 | 建议动作 |
|-----|-------|---------|
| 触发测试集（should-activate/should-not-activate） | 高 | `bench/scenarios/*.yaml` 新增 `trigger_test_cases` 字段 |
| CP Spec 作为独立编译器 IR（区别于最终 IR） | 高 | 新增 `specs/rnet/cp_spec_schema_v0.1.json` |
| 工具门禁 `forbidden_tools` | 中 | 在 `ECore` 或 `TCore` 新增 `forbidden_tools: string[]` |
| Protocol VM 熵向量暴露 | 中 | 在 `ValidationResult` 新增 `entropy_estimate` 对象 |
| 协议质量评分 Q(Skill) | 中 | 在 `BenchSummary` 新增 `skill_quality_score` 字段 |
| 对抗测试 Judge | 中 | `judge_spec` 新增 `adversarial` 类型 |
| 跨 Skill 组合（并联/循环） | 低 | `TCore` 新增 `next_skill` + `loop_condition` |
| Skill 治理字段 `governance` | 低 | `SkillPackage` 新增 `governance` 对象（含 org.owner/risk_tier/semver） |
| MetaIgnoranceProbe 触发规则 | 低 | `rnet_core` 补充触发条件说明 |

### 4.2 下一步工程实现优先级

根据 `specs/product/demo_repo_structure_v0.1.md` 的启动顺序建议：

```
Step 1  确认 specs/api/openapi_v0.1.yaml 字段定义（已完成）
Step 2  实现 runtime/compiler/ 7阶段管线
Step 3  用 examples/docs/ 三份文档跑通 /compile
Step 4  实现 runtime/executor/ + verifier（V1/V2/V3）
Step 5  跑通 /run（含 guardrail 拦截，对应 bench 场景中 blocked=true 的用例）
Step 6  实现 runtime/bench/，跑通 /bench
Step 7  开发 UI 三页（Compile/Run/Bench），以 specs/api/examples/ 为 mock 数据
Step 8  联调 + 路演彩排（见 wireframe_text_v0.1.md §路演彩排脚本）
```

---

## 五、文件修改规则（防止规范漂移）

### 5.1 单一真源原则

| 变更类型 | 操作顺序 |
|---------|---------|
| 修改字段**语义** | `docs/` → `rnet_core_v0.3.md` → `ir_schema_v0.3.json` → 更新所有 mapping 文件 |
| 修改字段**结构**（breaking） | `ir_schema`（bump 版本）→ `openapi_v0.1.yaml` → `judge_spec` → `scenario_spec` → `changelog` |
| 新增理论概念 | `docs/` → 评估是否需要落地 → `specs/rnet/` 新字段 |
| 新增 Bench 场景 | 新 `.yaml` 文件 → 验证符合 `scenario_spec_v0.1.json` → 更新 `changelog` |
| API 接口变更 | `openapi_v0.1.yaml` → `examples/` → `changelog`（必须标记 breaking） |

### 5.2 版本号规则

| 文件 | 当前版本 | Breaking Change 触发条件 |
|-----|---------|------------------------|
| `ir_schema_vX.json` | v0.3 | 增删改字段名/类型/必填性 |
| `openapi_vX.yaml` | v0.1 | 端点路径/请求响应字段变更 |
| `scenario_spec_vX.json` | v0.1 | 新增 required 字段 |
| `judge_spec_vX.md` | v0.1 | 算法变更/fatal 默认值变更 |

---

## 六、路演核心指标速查

从 `bench/scenarios/` 的 `metadata.expected_*` 字段汇总：

| 场景 | Vanilla 预期成功率 | MindLakeOS 预期成功率 | 核心差距 |
|------|-----------------|---------------------|---------|
| SOP 高峰期扩容门禁 | 20% | 90% | 门禁准确率：15% vs 95% |
| 政策报销审批矩阵 | 30% | 85% | 引用率：10% vs 95% |
| RFC API 网关设计 | 30% | 85% | schema 合规率：不稳定 vs 稳定 |

路演摘要卡目标（`sop-scale-guardrail` 场景）：
- **Token 节省 56%**（vs Vanilla）
- **成功率提升 +70%**（20% → 90%）
- **门禁准确率 95%**（vs Vanilla 15%）

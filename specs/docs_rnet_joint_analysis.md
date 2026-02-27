# `docs/` × `specs/rnet/` 联合分析

**文档目的**：阐明 `docs/` 理论文献与 `specs/rnet/` 工程规范之间的完整对应关系，供开发团队理解设计决策来源，以及识别当前规范的覆盖盲区。

**关联文件**：
- `docs/cognitive_compilation_agent_paradigm.md`
- `docs/cognitive_compilation_pet_unified.md`
- `docs/congintion-compilation.md`
- `docs/认知熵编译理论：AI Agent演化的统一框架.md`
- `specs/rnet/rnet_core_v0.3.md`
- `specs/rnet/ir_schema_v0.3.json`
- `specs/rnet/mapping_ui_v0.1.md`
- `specs/rnet/mapping_metrics_v0.1.md`

---

## 一、整体关系定位

```
docs/（理论层）                      specs/rnet/（工程规范层）
────────────────────────            ────────────────────────────────
为什么要设计 RNET？                   RNET 具体长什么样？
"熵"是什么？                          E 核字段如何定义？
"液态知识"是什么？                     SemanticKernelIR 结构是什么？
编译器做什么？                         编译器输出哪些字段？
协议运行时如何运转？                    RunResult / ValidationResult 结构是什么？
```

两者是**同一套思想在不同抽象层的表达**：`docs/` 提供理论依据与设计动机，`specs/rnet/` 将其落地为可校验、可实现的数据合同。

---

## 二、核心概念对应关系

### 2.1 认知编译三态 → RNET + 系统架构

`docs/cognitive_compilation_agent_paradigm.md` 提出知识的三态转化模型：

```
固态知识  ──Doc2Prompt──→  液态协议  ──LLM执行──→  气态Agent
（PDF/SOP）                （认知协议）              （运行中的执行体）
```

在 MindLakeVM 工程体系中的对应：

| 三态 | 理论定义 | 工程对应 |
|------|---------|---------|
| **固态** | 静止文档，高熵，需人读 | 编译器输入（`compile_request.document_content`） |
| **液态** | 可注入的结构化协议，低熵 | `SemanticKernelIR`（`ir_schema_v0.3.json` 完整定义） |
| **气态** | 运行中的 Agent，实时响应 | `RunResult`（trace + evidence + violations） |

> **结论**：`ir_schema_v0.3.json` 定义的 `SemanticKernelIR` 就是"液态知识"的精确数据结构。`specs/rnet/` 整个目录是"固态→液态"转换的输出规范。

---

### 2.2 PET 提示熵三分量 → RNET 四核

`docs/cognitive_compilation_pet_unified.md` 的核心公式：

$$H^*(P,C) = H_I(P,C) + H_S(P,C) + H_Y(P,C)$$

RNET 四核是这三个熵分量（加上执行路径熵）的工程实现：

| 熵分量 | 含义 | 消除机制 | 对应 RNET 核 | 关键字段 |
|--------|------|---------|------------|---------|
| **H_I**（意图歧义） | 用户意图不明确，模型猜测方向 | 语义坐标锚定 | **R 核** | `r.domain`、`r.object_type`、`r.semantic_space` |
| **H_S**（语义不确定性） | 任务允许多种解释，输出方向漂移 | 知识结构化注册，渐进披露 | **N 核** | `n.structure`、`n.schema`、`n.constraints`、`n.references` |
| **H_Y**（表面变异） | 输出格式不稳定，风格随机 | 可执行门禁与格式约束 | **E 核** | `e.format`、`e.hard_constraints`、`e.soft_constraints` |
| **执行路径熵**（PET 未命名） | 执行过程黑箱，步骤不可追溯 | 显式化执行路径 | **T 核** | `t.path[]`、`t.cot_steps` |

`rnet_core_v0.3.md` 中 E 核的字段名 `e.target_entropy`（"熵控目标"）直接来自 PET 的"熵减目标"概念，不是偶然命名。

---

### 2.3 认知协议结构模板 → `ir_schema_v0.3.json` 字段来源

`docs/cognitive_compilation_pet_unified.md` 附录 C 给出的标准认知协议 YAML 模板：

```yaml
contract:
  goal: "..."
  success_criteria: "..."
  anti_goals: ["..."]

io_schema:
  output:
    format: json
    schema: "..."

workflow:
  phases:
    - name: clarify
      gate: information_sufficient
    - name: execute
      tools: [...]
    - name: verify
      criteria: "..."

entropy_controls:
  H_I:
    tactics: [explicit_goal, negative_examples]
  H_S:
    tactics: [few_shot, constraints]
  H_Y:
    tactics: [strict_schema, low_temperature]
```

与 `ir_schema_v0.3.json` 的字段映射：

| 认知协议模板字段 | IR Schema 对应字段 | 说明 |
|---------------|------------------|------|
| `contract.goal` | `r.semantic_space` | 任务语义定位即合同目标 |
| `contract.anti_goals` | `e.hard_constraints` | 反目标 = 触发即拦截的红线 |
| `io_schema.output.format` | `e.format` | 输出格式约束 |
| `io_schema.output.schema` | `n.schema` | 输出 JSON Schema |
| `workflow.phases` | `t.path[]` | 执行阶段 = 路径步骤 |
| `workflow.phases[].gate` | `t.path[].decision_points[]` | 门禁 = 决策点条件 |
| `workflow.phases[].tools` | `t.path[].tool_required` | 工具调用绑定 |
| `entropy_controls.H_Y[strict_schema]` | `n.schema` + `e.format=json` | 格式熵控的双重保障 |
| `entropy_controls.H_S[constraints]` | `n.constraints` | 语义约束列表 |

---

### 2.4 Cognitive Compiler 6 阶段 → IR 四核填充顺序

`docs/cognitive_compilation_pet_unified.md` §7.1 的编译流水线：

```
Parse → Extract → Normalize → Validate → Optimize → Package
```

每个阶段对应 IR 的填充内容：

| 编译阶段 | 熵操作（PET 视角） | 填充的 RNET 字段 |
|---------|-----------------|----------------|
| **Parse** | 降低文档结构熵 | `r.domain`、`r.object_type`（文档类型识别） |
| **Extract** | 降低信息冗余熵 | `t.path[]`（步骤提取）、`e.hard_constraints`（红线提取） |
| **Normalize** | 降低术语歧义熵（H_I） | `r.semantic_space`（语义定位）、`n.constraints`（字段约束消歧） |
| **Validate** | 检测逻辑熵（矛盾/缺失） | `validation.schema_valid` / `validation.evidence_sufficient` |
| **Optimize** | 降低表达冗余熵 | `n.references[]`（渐进披露分层）、`e.soft_constraints`（降级策略） |
| **Package** | 标准化接口熵 | `SkillPackage.files_tree`（Skill 目录生成） |

`enable_probe=true` 时额外触发 **MetaIgnoranceProbe**，填充 `e.meta_ignorance`——对应 PET 中"识别剩余不可知熵"的概念。

---

### 2.5 协议成熟度 L1-L4 → MindLakeVM 在其中的定位

`docs/cognitive_compilation_pet_unified.md` §5.4 定义协议成熟度分级：

| 等级 | 名称 | 特征 | 熵状态 |
|-----|------|------|-------|
| L1 | 咒语型 | "你是一个有用的助手..." | 高熵，依赖模型随机性 |
| L2 | 框架型 | 角色 + 背景 + 任务（CO-STAR 等） | 中熵，有初步结构 |
| L3 | 算法型 | 分支判断 + 自检循环 + CoT | 中低熵，具备逻辑流 |
| L4 | 协议型 | 标准化 I/O + 错误处理 + 可组合 | 低熵，可编译、可回归 |

MindLakeVM 通过 RNET 四核生成的 Skill 定位在 **L4**：

- **标准化 I/O**：`n.schema`（输入约束）+ `e.format`（输出格式）
- **错误处理**：`e.hard_constraints`（触发即拦截）+ `validation`（V1/V2/V3）
- **可组合**：`n.references[]`（模块化引用）+ `t.path[]`（可测试步骤）
- **可回归**：`bench/scenarios/*.yaml`（对应 PET 的"协议回归测试集"）

Vanilla 和 RAG 等价于 L1~L2，这正是 Bench 对比要展示的差距。

---

### 2.6 协议设计五原则 → RNET 字段设计对应

`docs/cognitive_compilation_agent_paradigm.md` §5.1 的五大设计原则：

| 原则 | 定义 | 在 `specs/rnet/` 中的体现 |
|-----|------|------------------------|
| **单一职责** | 每个协议只做一件事 | `r.domain` + `r.object_type` 精确限定 Skill 边界 |
| **显式优于隐式** | 决策条件必须写明 | `t.path[].decision_points[]` 显式化每个分支 |
| **边界明确** | 定义"能做什么"和"不能做什么" | `e.hard_constraints`（不能做）+ `e.meta_ignorance`（不知道边界） |
| **可组合性** | 协议间能互相调用、串联 | `n.references[]` 模块化查表层；`t.path[]` 步骤粒度可测试 |
| **可验证性** | 执行结果能被检验 | V1/V2/V3 三验证器 + `bench/judge_spec_v0.1.md` |

---

## 三、`docs/` 有、`specs/rnet/` 尚未完全覆盖的理论点

以下是当前规范的空白区，是 v0.4 迭代的候选方向：

### 3.1 Protocol VM 四维熵向量（高优先级）

`docs/cognitive_compilation_pet_unified.md` §6.2 定义运行时状态：

$$S = \langle P, C, A, H, \kappa \rangle, \quad H = \langle H_p, H_a, H_i, H_c \rangle$$

当前 `RunResult.validation` 只有 `schema_valid` / `evidence_sufficient` / `stop_condition_met`，**没有暴露实时熵向量**。

**补充建议**：在 `ir_schema_v0.4.json` 的 `ValidationResult` 中加入：
```json
"entropy_estimate": {
  "h_intent": null,
  "h_semantic": null,
  "h_surface": null,
  "h_path": null
}
```
可在路演中直观展示"执行过程中熵如何下降"。

---

### 3.2 协议组合代数（中优先级）

`docs/cognitive_compilation_pet_unified.md` §10.3 提出四种组合：

| 组合方式 | 形式 | 当前 `specs/rnet/` 支持情况 |
|---------|------|--------------------------|
| 顺序组合 P1 ; P2 | T.path 线性链 | ✅ 已支持（`t.path[]` 有序列表） |
| 条件组合 if C then P1 | `decision_points` | ✅ 部分支持（步骤内决策点） |
| 并行组合 P1 \|\| P2 | 多 Skill 并行执行 | ❌ 未支持 |
| 跨 Skill 调用 | `tool_required` 调用另一 Skill | ❌ 未支持（只能调用工具） |
| 循环组合 while C do P | V3 停止规则 | ⚠️ 隐式支持（停止条件未显式建模） |

**补充建议**：在 `t.path[].next_skill` 字段支持跨 Skill 组合，以及 `t.loop_condition` 支持显式循环。

---

### 3.3 熵效率作为编译质量指标（中优先级）

`docs/cognitive_compilation_pet_unified.md` §5.5 定义协议质量公式：

$$Q(Protocol) = \frac{H_\phi^{before} - H_\phi^{after}}{C_{engineering} + \lambda \cdot C_{execution}}$$

当前 `BenchSummary` 有 `token_savings_pct` 和 `success_rate_delta`，但**没有直接的"熵效率"指标**。

`token_savings_pct` 是 $C_{execution}$ 的代理指标，`success_rate_delta` 是 $\Delta H_\phi$ 的代理指标，但两者没有被结合为统一的 Q 值。

**补充建议**：在 `BenchSummary` 增加 `protocol_quality_score`，计算方式：
```
protocol_quality_score = success_rate_delta / (1 - token_savings_pct)
```

---

### 3.4 MetaIgnoranceProbe 的触发规则（低优先级）

`e.meta_ignorance` 字段已在 `ir_schema_v0.3.json` 中定义，但 `rnet_core_v0.3.md` 没有说明"编译器应在什么条件下填充这个字段"。

理论上 `docs/` 中的"未知的已知（Unknown Knowns）"对应这里——编译器识别到的"文档存在但未覆盖的相关问题域"。

**补充建议**：在 `rnet_core` 补充 MetaIgnoranceProbe 的触发条件规范（v0.4 待办）。

---

## 四、两个目录的"单一真源"分工

```
docs/
  ├── cognitive_compilation_agent_paradigm.md   ← 三态模型、协议工程学的哲学基础
  ├── cognitive_compilation_pet_unified.md       ← PET 信息论 + 统一框架的数学基础
  ├── congintion-compilation.md                  ← 认知编译的综合扩展讨论
  └── 认知熵编译理论：AI Agent演化的统一框架.md   ← 统一框架的中文版论述

specs/rnet/
  ├── rnet_core_v0.3.md        ← 四核字段语义的工程定义（SSoT：字段含义）
  ├── ir_schema_v0.3.json      ← 四核数据结构的 JSON Schema（SSoT：数据结构）
  ├── mapping_ui_v0.1.md       ← 理论字段 → UI 元素的映射（SSoT：前端绑定）
  └── mapping_metrics_v0.1.md  ← 理论字段 → Bench 指标的映射（SSoT：评测口径）
```

**规则**：
- 修改字段**语义**：先改 `docs/` 理论文档，再改 `rnet_core_v0.3.md`，最后改 `ir_schema_v0.3.json`
- 修改字段**结构**（breaking change）：先改 `ir_schema`，更新版本号，记录到 `specs/changelog/specs_changelog.md`
- 新增理论概念：先写入 `docs/`，评估是否需要在 `specs/rnet/` 落地，再决定是否加字段

---

## 五、一句话总结（路演口径）

> **`docs/` 解释"RNET 为何这样设计"，`specs/rnet/` 定义"RNET 具体长什么样"。**
> 
> RNET 四核 = PET 熵三分量（H_I/H_S/H_Y）+ 执行路径熵 的工程实现。
> `ir_schema_v0.3.json` = "液态知识"的精确数据结构合同。
> MindLakeVM 的 Skill = L4 级认知协议，是 Bench 对比中 Vanilla（L1）和 RAG（L2）无法企及的原因。

# RNET 四核与中间表示（IR）的关系：原理、实现与边界

## 1. 文档目标

本文回答六个问题：

- `RNET 四核` 与 `SemanticKernelIR` 的关系是什么？
- 编译阶段如何把文档转换成四核 IR？
- 运行阶段四核分别如何被消费？
- Simple Runner 与 Agent Runner 的执行语义有何区别？
- 当前实现与 schema/spec 有哪些差异或风险？
- IR 如何对外发布并被外部系统复用？

结论先行：

> 在 MindLakeVM 中，**IR 是统一数据载体**，**R/N/E/T 四核是 IR 内部的语义分层**。  
> 系统行为不是由“自由提示词”直接决定，而是由“编译出的 IR 结构”决定。


## 2. 定义层关系：四核是 IR 的骨架

### 2.1 Schema（规范）

`specs/rnet/ir_schema_v0.3.json` 定义：

- 顶层对象 `SemanticKernelIR`
- 顶层必填：`kernel_id`、`version`、`r`、`n`、`e`、`t`

可抽象为：

`SemanticKernelIR = Header + RCore + NCore + ECore + TCore`

### 2.2 Runtime Model（实现）

`mindlakevm/runtime/models.py` 的 `SemanticKernelIR` 与 schema 对齐，包含：

- `r: RCore`
- `n: NCore`
- `e: ECore`
- `t: TCore`

因此四核与 IR 的关系是“字段层次关系”，不是并列概念。


## 3. 四核职责分工

结合 `specs/rnet/rnet_core_v0.3.md`：

1. `R（Representation）`：语义坐标  
   字段：`r.domain`、`r.object_type`、`r.semantic_space`  
   作用：锚定“这项技能属于哪个领域、解决什么问题”。

2. `N（Notation）`：知识注册  
   字段：`n.structure`、`n.schema`、`n.constraints`、`n.references`  
   作用：把文档组织成可约束、可引用、可验证的资产结构。

3. `E（Entropy Control）`：熵控门禁  
   字段：`e.format`、`e.target_entropy`、`e.hard_constraints`、`e.soft_constraints`、`e.meta_ignorance`  
   作用：定义红线、降级规则、盲点边界。

4. `T（Transformation）`：执行路径  
   字段：`t.path`、`t.cot_steps`（含 `decision_points`、`tool_required`）  
   作用：把执行过程显式化为步骤与分支。


## 4. 编译原理：文档语义如何进入 IR

入口：`mindlakevm/runtime/compiler/pipeline.py::compile_document()`

工程流水线（实现命名）：

1. `Ingest`：标准化输入
2. `Classify`：关键词分类（影响 `r.object_type`）
3. `Extract + Synthesize`：LLM 生成四核 IR
4. `Package`：生成 `SkillPackage`

核心机制：`COMPILE_IR_TOOL`（`generate_semantic_kernel_ir`）  
编译器用 tool schema 约束 LLM 输出的结构，降低 JSON 漂移与漏字段问题。


## 5. 术语对照：理论阶段 vs 当前实现

`specs/docs_rnet_joint_analysis.md` 使用理论流水线：

`Parse -> Extract -> Normalize -> Validate -> Optimize -> Package`

当前 `pipeline.py` 的近似映射：

| 理论阶段 | 当前实现近似阶段 | 主要落点字段 |
|---|---|---|
| Parse | Ingest + Classify | `r.domain` / `r.object_type` |
| Extract | Extract | `t.path`、`e.hard_constraints` |
| Normalize | Synthesize | `r.semantic_space`、`n.constraints` |
| Validate | 运行时 verify（非 compile 强校验） | `validation.*` |
| Optimize | Synthesize + Package | `n.references`、`e.soft_constraints` |
| Package | Package | `SkillPackage.files_tree` |

注意：当前实现中，`Validate` 主要发生在 run 阶段（`verifier.py`），不是 compile 阶段的强一致校验。


## 6. 运行原理：四核如何被执行器消费

### 6.1 E 核先行（能不能做）

`runner.py` 首先执行 `check_guardrails(ir.e, user_input)`：

- 命中硬约束 -> `blocked=true`，返回 `violations`
- 不命中 -> 进入后续生成

这对应 E 核“先门禁后执行”。

### 6.2 T 核驱动（按什么路径做）

`t.path` 决定 trace 的步骤骨架：

- `make_trace()` 基于 `PathStep` 生成 `TraceStep`
- `decision_taken` 记录关键判断

### 6.3 N 核约束（怎么证明做对了）

验证器 `verifier.py` 使用 N 核做两类校验：

- V1：`e.format=json` 且 `n.schema` 存在时，做 schema 校验
- V2：`n.references[].required=true` 必须在 evidence 中出现

### 6.4 R 核定位（这个 Skill 是什么）

`skills.py`、`tool_export.py` 通过 R 核构建：

- 技能摘要（domain/object_type/semantic_space）
- Tool Search 元数据
- 对外 tool description


## 7. 执行语义差异：Simple Runner vs Agent Runner

两种执行器不是同一种 trace/evidence 语义，应区分理解：

1. `Simple Runner`（`executor/runner.py`）
- 单次 LLM 调用
- trace 由 `t.path` 事后填充（模拟完成态）
- evidence 主要靠关键词启发式收集

2. `Agent Runner`（`executor/agent_runner.py`）
- 多轮 tool loop
- 可调用内置工具：`step_complete`、`report_decision`、`cite_reference`
- trace/evidence 来自显式工具调用，语义更接近“真实执行轨迹”


## 8. 规范-实现差异与当前风险

### 8.1 `hard_constraints` 必填约束差异

- Schema：`ECore.required` 包含 `hard_constraints`
- `COMPILE_IR_TOOL`：`e.required` 当前未强制 `hard_constraints`

影响：编译产物可能出现“E 核缺少红线”的弱门禁配置，降低拦截可靠性。

### 8.2 compile 阶段缺少强 schema 校验

`compile_document()` 最终依赖 `SemanticKernelIR(**raw)`，但没有对 `ir_schema_v0.3.json` 做显式 JSON Schema 校验。  
这会导致“规范层约束”与“运行时接受条件”之间可能出现漂移。

### 8.3 Simple Runner 的 evidence 非强保证

`_collect_evidence()` 基于文件名关键词匹配，不是条款级引用解析。  
因此 V2 的通过/失败在某些场景下可能受启发式误差影响。


## 9. IR 对外发布与复用路径

IR 不只是内部对象，也有标准对外出口：

1. API 资源
- `GET /skills/{skill_id}`：返回完整 `ir`
- `GET /skills/{skill_id}/tool`：导出 Claude/MCP/search/bundle 格式

2. MCP 资源
- `skill://{skill_id}/ir`：完整 IR
- `skill://{skill_id}/summary`：结构化摘要
- `skill://{skill_id}/tool`：Tool Definition

3. 存储形态
- `store.py` 将 `ir + package` 持久化为 `$SKILLS_DIR/<skill_id>.json`


## 10. 最小端到端示例

### 10.1 输入（compile）

示例任务：`编译 Sev1 事故响应 SOP`

### 10.2 编译输出（IR 片段）

```json
{
  "r": {
    "domain": "ops.incident",
    "object_type": "sop",
    "semantic_space": "Sev1 事故响应流程，面向 SRE"
  },
  "e": {
    "format": "markdown",
    "target_entropy": "降低故障处置不确定性",
    "hard_constraints": ["高峰期禁止扩容，除非 CTO 书面授权"]
  },
  "t": {
    "path": [
      {"id": "detect", "name": "故障检测", "description": "确认影响范围"}
    ]
  }
}
```

### 10.3 执行输出（run 结果形态）

- 合规请求：`blocked=false`，返回 `trace + evidence + validation`
- 违规请求：`blocked=true`，`violations` 标明触发的硬约束

这展示了“编译时定义边界，运行时执行边界”的完整闭环。


## 11. 与传统编译器 IR 的区别

相同点：

- 都遵循“源输入 -> IR -> 执行”的工程范式
- 都追求稳定接口和可处理性

不同点：

- 传统 IR（SSA/三地址码）关注机器计算语义
- RNET IR 关注 Agent 认知执行语义（约束、路径、证据、门禁）

简化理解：

- 传统 IR 回答“怎么算”
- RNET IR 回答“怎么在边界内思考并执行”


## 12. 一句话总结

MindLakeVM 的核心不是“把文档塞进 prompt”，而是：

- 用 R/N/E/T 四核把知识编译成 `SemanticKernelIR`
- 再让执行器按 IR 的结构化约束去运行、校验、追踪、导出

这就是“认知编译”的工程化落地。

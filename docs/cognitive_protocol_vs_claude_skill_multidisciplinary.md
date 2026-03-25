# 认知协议规范 vs Claude Agent Skill：跨学科本质比较

## 1. 文档目的

本文从多个学科抽象层面比较两类规范：

- **Claude Agent Skill**（能力声明范式）——以 Tool Definition + Tool Use Examples + Programmatic Tool Calling 为代表
- **MindLakeVM 认知协议规范**（RNET IR 范式）——以 SemanticKernel IR 四核（R/N/E/T）为代表

目标不是做产品优劣评测，而是回答一个更本质的问题：

**它们分别在规范什么？这种差异在哪些学科视角下可被严格刻画？**

本文结合 MindLakeVM 项目的理论文献（PET 提示熵理论、SKT 语义核理论、EA-SKT 高熵分叉点理论）和工程实现（`specs/rnet/`、`mindlakevm/runtime/`），给出跨越十余个学科的系统性比较，并在最后提出统一映射表与工程启发。

**参考来源**：
- Anthropic, *Introducing advanced tool use on the Claude Developer Platform*, 2025-11-24
- MindLakeVM 理论文献（`docs/`）、工程规范（`specs/rnet/`）、运行时实现（`mindlakevm/runtime/`）
- EA-SKT: *Beyond the 80/20 Rule: High-Entropy Minority Tokens Drive Effective RL for LLM Reasoning*, arXiv 2506.01939


## 2. 核心结论（先给结论）

一句话：

> **Agent Skill 主要规范"可调用能力"，认知协议规范主要规范"可验证决策过程"。**

因此两者不是同层替代关系，而是**分层互补关系**：

| 维度 | Skill | 认知协议 |
|------|-------|---------|
| 抽象层 | 能力接口层（capability layer） | 控制与治理层（control/governance layer） |
| 核心产物 | Tool Definition（JSON Schema） | SemanticKernel IR（RNET 四核状态机） |
| 回答的问题 | 能做什么、如何调用 | 为什么这样做、什么不能做、如何证明做对 |
| 优化目标 | 调用准确率、token 效率 | 降熵量、合规覆盖率、可追溯性 |
| 知识形态 | 函数签名 + 示例 | 四核 IR（语义/注册/门禁/路径） |

## 3. 统一形式化表达

将两者抽象为两个对象：

### 3.1 能力契约（Skill）

`Skill := <name, input_schema, output_schema, examples>`

它回答：

- 能做什么（name + description）
- 如何调用（input_schema）
- 参数格式是什么（JSON Schema + examples）

在 Anthropic Advanced Tool Use（2025.11）之后，Skill 还包括 `input_examples`（1-5 个使用示例）和 `defer_loading`（按需发现），但其本质仍是**声明式接口描述**——形式化维度为 4。

### 3.2 认知契约（Protocol）

`Protocol := <S, T, G, E, V, J>`

其中：

- `S`：状态空间（任务语义坐标）—— 对应 RNET **R 核**（`r.domain` / `r.semantic_space`）
- `T`：状态转移规则（步骤、分支、决策点）—— 对应 RNET **T 核**（`t.path` / `t.cot_steps`）
- `G`：约束集合（红线、软约束、盲点声明）—— 对应 RNET **E 核**（`e.hard_constraints` / `e.meta_ignorance`）
- `E`：证据机制（引用与可追溯）—— 对应 RNET **N 核**（`n.references`）
- `V`：验证机制（输出 Schema、引用充分性、停止条件）—— V1/V2/V3 三重校验
- `J`：目标函数（降熵、成功率、成本等）—— PET 熵预算

它回答：

- 为什么这样做（T 核 decision_points + cot_steps）
- 什么不能做（E 核 hard_constraints + meta_ignorance）
- 如何证明做对（V1 Schema + V2 引用充分性 + V3 停止规则）

### 3.3 关键结构差异

Skill 的形式化维度为 4（名称、输入、输出、示例），Protocol 的形式化维度为 6。**多出的两个维度——约束 G 和验证 V——正是"治理能力"的数学载体。**

- 没有 G，系统无法表达"不可做"
- 没有 V，系统无法证明"做对了"

这两个维度的缺失，是后续所有学科视角中 Skill 与 Protocol 分歧的形式化根源。


## 4. 从计算机科学看本质差异

### 4.1 编程语言视角

- Skill 类似函数签名与调用示例（接口定义）
- 认知协议类似操作语义 + 约束系统（行为定义）

对应关系：

| 概念 | Skill 对应 | 协议对应 |
|------|-----------|---------|
| 类型系统 | `type/interface contract` | `dependent type + refinement type` |
| 语义学 | 指称语义（函数映射） | 操作语义（状态转移 + 安全约束） |
| 验证 | 类型检查（参数是否合法） | 模型检查（执行路径是否满足不变量） |

Skill 的 JSON Schema 等价于简单类型系统——只约束"输入的形状"。协议的 E 核 hard_constraints + T 核 decision_points 等价于**依赖类型 + 精化类型**——约束"值域的语义边界"和"状态转移的合法性"。

在 Anthropic Programmatic Tool Calling（PTC）出现后，Claude 可以写 Python 代码编排多个 Tool，这让执行层的透明性提升了。但 PTC 的代码是**运行时即兴生成的**，不是编译时预定义的——相当于 JIT 解释执行，而协议的 `t.path` 是 AOT 编译产物，可版本化、可回归测试。

### 4.2 系统架构视角

- Skill 偏插件目录（tool catalog）
- 协议偏执行内核（execution kernel）

前者强调"可扩展能力数量"，后者强调"执行一致性与可控性"。

具体到 MindLakeVM 架构：

```
Skill 范式：  User → LLM → Tool Catalog → Tool 1..N → 输出（无预检、无追溯）
协议范式：  User → guardrail(E核) → LLM(T核驱动) → evidence(N核) → verify(V1/V2/V3) → 结构化输出
```

### 4.3 编译器与 IR 视角

这是两者最深层的计算机科学差异：

- Skill 没有"编译"概念——开发者手写 Tool Definition，直接使用
- 协议有完整的编译管线：`文档 → Ingest → Classify → Extract → Synthesize → Package → IR`

传统编译器 IR（如 LLVM IR / SSA）关注**机器计算语义**（寄存器分配、控制流图），RNET IR 关注**认知执行语义**（约束、路径、证据、门禁）。

两者共享同一工程范式：**源输入 → IR → 执行**，但 IR 的语义空间完全不同。这意味着认知协议可以复用编译器工程的成熟方法论（优化 pass、验证 pass、版本兼容性），而 Skill 没有这个工程支撑。


## 5. 从控制论看本质差异

- Skill 主要提供动作集合 `A`
- 协议定义控制律 `u = pi(s)` 和约束域 `s ∈ SafeSet`

即：

- Skill 更像执行器清单
- 协议更像闭环控制器（含反馈）

在 MindLakeVM 中，`guardrail + trace + evidence + verify` 形成闭环反馈结构，这不是普通 tool schema 自动具备的属性。


## 6. 从信息论看本质差异

Skill 主要增加“可选操作”，但不直接规定如何压缩不确定性来源。  
认知协议把不确定性分解并施加结构化约束，目标是压缩可优化项：

`H_phi = H_min + D_KL + I_wasted`

可理解为：

- Skill：扩展动作空间
- 协议：收缩有效搜索空间

后者更接近“在约束下优化分布距离”的问题。


## 7. 从统计学习看本质差异

- Skill 提供特征/工具入口，但不保证统计充分性
- 协议追求“接近充分统计量”的接口表达（高质量 R/N/E/T）

因此协议型规范天然关心：

- 自洽率（SCR）
- 语义聚类熵（SCE）
- 证据覆盖率

而不只关心“有没有调用工具”。


## 8. 从决策理论看本质差异

- Skill：定义“可行动作”
- 协议：定义“动作可行域 + 风险约束 + 分支准则”

前者偏 action availability，后者偏 policy admissibility。  
当场景存在高风险误操作时，只有后者能把“不可做”显式写进系统状态机。


## 9. 从认知科学看本质差异

类比人类认知架构：

- Skill 对应“会使用哪些工具”
- 协议对应“执行功能系统”（计划、抑制、监控、校验）

认知协议的价值不是让模型“更会说”，而是让模型在复杂任务中“更像有执行功能的系统”。


## 10. 从语言学与符号学看本质差异

- Skill 偏语用层（如何触发某个行为）
- 协议覆盖语义层与语用层（意义边界 + 执行规则）

Skill 依赖模型对描述文本的隐式理解；  
协议将关键边界显式编码，减少“同词异义/语境漂移”。


## 11. 从法学与治理看本质差异

- Skill 便于说明“执行了什么”
- 协议便于审计“为何可执行、为何被拦截”

在合规语境里，这对应：

- 事后解释（post-hoc explanation）
- 事前约束（ex-ante governance）

认知协议属于后者，治理强度更高。


## 12. 从组织科学看本质差异

- Skill 像“个人技能清单”
- 协议像“组织 SOP + 风险控制流程”

组织可复制性取决于后者：  
因为协议可版本化、可回归、可培训，而不仅依赖个体提示技巧。


## 13. 从经济学看本质差异

- Skill：前期成本低、上线快、边际不确定性高
- 协议：前期建模成本高、复用期稳定性收益高

适用性可按风险与复用频次判断：

- 低风险、一次性任务：Skill 优先
- 高风险、高复用任务：协议优先


## 14. 从哲学（规范性）看本质差异

Skill 回答“能做什么”（is/can）。  
协议回答“应做什么、禁做什么、如何证明”（ought/must）。

因此协议本质上是把“规范性理性”编码进执行系统，  
而 Skill 更多是“工具性理性”的接口化表达。


## 15. 对 MindLakeVM 的具体启发

在本项目中，两者最优关系不是二选一，而是分层耦合：

1. 以 Skill 提供能力表面（对外可调用）
2. 以 RNET IR 提供执行内核（对内可控）
3. 以 verifier/bench 提供可验证回路（可审计）

可抽象为：

`Capability Layer (Skill) -> Control Layer (RNET Protocol) -> Assurance Layer (Verify/Bench)`


## 16. 结语

从跨学科本质看：

- Claude Agent Skill 解决“能力接入问题”
- 认知协议规范解决“认知治理问题”

前者让系统“能做事”，后者让系统“可控地做对事”。  
在高风险 Agent 系统中，后者是规模化落地的必要条件。


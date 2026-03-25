# MindLakeVM 项目优化文档（EA-SKT 视角）

## 1. 文档目的

本文给出面向 MindLakeVM 的优化路线图，目标是把 EA-SKT（Token 熵感知语义核理论）的关键结论落到现有工程实现中，提升三类能力：

- 稳定性：减少高风险场景下的推理漂移
- 可验证性：让 trace / evidence / validation 更接近真实执行语义
- 经济性：把算力和 token 预算集中在关键决策点


## 2. 当前系统基线（简述）

当前系统已经具备完整闭环：

- 编译：`/compile` 将文档编译为 `SemanticKernelIR`（R/N/E/T）
- 执行：`/run` 支持 Simple Runner 与 Agent Runner
- 治理：E 核门禁、V1/V2/V3 验证、trace/evidence 输出
- 对外：`/skills/{id}/tool` 与 MCP `skill://{id}/ir` 资源导出

但从 EA-SKT 视角，仍有优化空间：

- 对“高熵分叉点”的识别与控制还不够显式
- compile 与 run 的校验强度存在层间不一致
- evidence 在 Simple Runner 中仍偏启发式


## 3. EA-SKT 对本项目的工程含义

EA-SKT 的核心可转为三条工程原则：

1. 关键少数原则  
少数高熵 token/决策点承载主要推理质量。工程上应优先优化 `E/T`，而不是平均优化所有步骤。

2. 结构先验原则  
高质量语义核（尤其 E/T）可在推理前约束状态空间，减少运行时漂移和无效探索。

3. 双侧协同原则  
训练侧（RLVR）与推理侧（IR 编译 + 执行约束）应围绕同一“分叉点质量”指标协同优化。


## 4. 优化目标（2026 Q1-Q2）

### 4.1 目标 O1：分叉点显式化

把“关键决策点”从隐式提示升级为可编译、可追踪、可评测的结构对象。

### 4.2 目标 O2：校验前移 + 执行闭环

在 compile 阶段引入更强 schema/约束校验，减少“运行时才发现配置不完整”的情况。

### 4.3 目标 O3：证据质量升级

从“关键词命中”逐步走向“决策点绑定证据”。

### 4.4 目标 O4：指标体系升级

在成功率之外，新增“分叉点质量”和“熵收敛”类指标。

### 4.5 目标 O5：分布距离可观测化

将“语义核质量”转为可计算的分布偏差指标，支持诊断、回归和自动优化。


### 4.6 两篇文档的融合结论

本路线图额外吸收以下两份文档的核心主张：

- `/Users/mindlake/Downloads/语义核理论_学术论文.docx`
- `/Users/mindlake/Downloads/语义核与分布距离.md`

融合后的工程化结论：

1. 语义核不是提示技巧，而是输出分布上的算子  
`P_actual -> P_kappa`，优化目标是最小化 `d(P_kappa, P_ideal)`。

2. 四核对应四类主要偏差  
- `R`：支撑集偏差（TV/Wasserstein）
- `N`：条件结构偏差（KL/Renyi）
- `E`：集中度偏差（JS）
- `T`：路径传输偏差（Wasserstein）

3. 三分量仍是总目标函数  
`H_phi = H_min + D_KL(P_ideal || P_actual) + I_wasted`  
其中可优化部分主要是后两项，且 `I_wasted` 主要由 `N/T` 影响。

4. 充分统计量是“质量上限”定义  
实践上难以直接验证，可用 `SCR/SCE/扰动稳定性` 作为代理近似。


## 5. 分模块优化方案

## 5.1 编译器层（`runtime/compiler/`）

### 方案 A：强化 E 核必填一致性

- 现状：`ir_schema_v0.3.json` 要求 `e.hard_constraints` 必填，但 `COMPILE_IR_TOOL` 未强制
- 动作：
  - 对齐 `COMPILE_IR_TOOL` 与 schema 的 required 约束
  - 在 `_extract_ir()` 结束后补充 JSON Schema 校验（失败则回退重试或返回 422）

### 方案 B：新增分叉点提取字段（兼容扩展）

- 在不破坏现有 `DecisionPoint` 结构前提下，新增可选元信息：
  - `entropy_level`: `low|mid|high`
  - `decision_criticality`: `p1|p2|p3`
  - `evidence_required_scopes`: `list[str]`
- 用途：
  - 运行时做差异化控制
  - 评测时统计“关键决策点覆盖率”

### 方案 C：E/T 质量评分内置

- compile 结果附加 `quality_report`（可选）：
  - `r_score/n_score/e_score/t_score`
  - `fork_point_count`
  - `high_criticality_ratio`
  - `distance_proxy`（新增，见方案 L）
- 用于后续 RLVR 数据筛选和 prompt 诊断。


## 5.2 执行器层（`runtime/executor/`）

### 方案 D：分叉点驱动执行策略

- 在 `agent_runner` 中，当命中 `decision_criticality=p1`：
  - 强制调用 `report_decision`
  - 强制完成至少一条 `cite_reference`（若 `evidence_required_scopes` 非空）
  - 未满足则不允许 `step_complete`

### 方案 E：Simple Runner 最小可信升级

- 保持单轮调用低延迟优势，同时增加：
  - `required` references 的明确覆盖检查
  - evidence 命中置信度分级（`low/mid/high`）
  - 输出中增加“证据不足降级提示”

### 方案 F：熵感知路由（可选）

- 新增 `run_mode=auto`：
  - 低风险请求走 Simple Runner
  - 高风险/高分叉密度请求走 Agent Runner
- 路由依据：
  - `E/T` 评分
  - `decision_criticality` 统计
  - 历史 block/violation 模式


## 5.3 验证器层（`runtime/executor/verifier.py`）

### 方案 G：V2 从“文件级”到“决策级”

- 当前：required references 是否出现
- 升级：每个关键决策点是否有对应 scope 的证据项

### 方案 H：新增 V4（决策完备性）

- 检查项：
  - 所有 `p1` 决策点是否有 `report_decision`
  - `if_true/if_false` 分支是否在 trace 中可追溯

### 方案 I：新增 V5（输出熵代理）

- 用可计算代理指标近似评估“收敛性”：
  - 多次采样输出的语义聚类熵（SCE）
  - 自洽率（SCR）


## 5.4 API 与对外协议层（`runtime/api/`, `mcp_server.py`）

### 方案 J：新增诊断端点

- `POST /diagnose_prompt_entropy`
  - 输入：任务 + 提示/IR
  - 输出：R/N/E/T 评分 + 分叉点密度 + 风险建议

### 方案 K：Skill 详情扩展

- `GET /skills/{id}` 返回可选 `quality_report`
- `skill://{id}/summary` 增加分叉点统计与关键决策点摘要


## 5.5 度量层（新增）

### 方案 L：四核-距离映射的代理度量落地

为避免依赖不可观测的真实分布，先采用可计算代理：

- `R 核（表示）`：
  - 代理：主题偏移率、任务类型误分类率
  - 目标：降低支撑集偏移（TV proxy）

- `N 核（注册）`：
  - 代理：required 字段缺失率、required reference 漏引率
  - 目标：降低条件结构偏差（KL proxy）

- `E 核（熵）`：
  - 代理：多次采样答案分散度、违规边界穿透率
  - 目标：降低混合代价（JS proxy）

- `T 核（转换）`：
  - 代理：关键决策点偏航率、步骤跳跃率、分支错误率
  - 目标：降低路径传输代价（W1 proxy）

### 方案 M：诊断决策树（运行时/评测复用）

新增统一诊断规则：

- “答非所问”优先归因 R 核
- “高方差同题多解”优先归因 E 核
- “遗漏特定正确类别”优先归因 N 核
- “路径错误但偶尔答对”优先归因 T 核
- “上下文丰富但未利用”归因 `I_wasted`（重点看 N+T）

该规则来自《语义核与分布距离》中的度量选择原则，可直接写入评测器判定逻辑。


## 6. Bench 与指标体系优化

## 6.1 新增核心指标

- `Fork Coverage`：高关键决策点被显式记录并验证的比例
- `Decision Evidence Precision`：决策点证据匹配准确率
- `SCR`：Self-Consistency Rate
- `SCE`：Semantic Cluster Entropy（越低越好）
- `Guardrail Precision/Recall`：从 block rate 升级为精准率/召回率
- `I_wasted Proxy`：上下文可用信息未被利用的估计比例
- `R/N/E/T Distance Proxy`：四核对应偏差的代理分值

## 6.2 对比基线建议

- Vanilla Prompt
- CoT / Self-Consistency
- 当前 MindLakeVM（v0）
- EA-SKT 优化版 MindLakeVM（v1）

要求输出统一报告：准确率、成本、时延、可追溯性四维对比。

并新增“分布偏差雷达图”：

- R 偏差（TV proxy）
- N 偏差（KL proxy）
- E 偏差（JS proxy）
- T 偏差（W1 proxy）

用于可视化不同策略到底在“哪里变好”。


## 7. 实施计划（建议）

## 7.1 Phase 1（1-2 周）：一致性与低风险增强

- 对齐 compile tool required 与 schema required
- compile 后新增 schema 校验
- Simple Runner evidence 置信度分级
- 增加基础质量评分输出

验收标准：

- schema mismatch 类错误下降
- block/violation 解释完整率提升

## 7.2 Phase 2（2-4 周）：分叉点显式控制

- 扩展 decision point 元信息
- Agent Runner 强制关键决策点记录与证据门禁
- verifier 增加 V4（决策完备性）

验收标准：

- 关键决策点 trace 覆盖率 > 90%
- required scope 证据满足率显著提升

## 7.3 Phase 3（4-8 周）：熵指标与自动路由

- Bench 接入 SCR/SCE
- 实现 `run_mode=auto`
- 新增 `/diagnose_prompt_entropy`
- 接入四核距离代理评分与偏差雷达图

验收标准：

- 在同等质量下 token 成本下降
- 高风险场景 success rate 与 guardrail precision 同时提升
- `I_wasted Proxy` 下降且不牺牲成功率


## 8. 风险与控制

- 风险 R1：规则过严导致可用性下降  
控制：提供降级策略与模式开关（strict / balanced / fast）。

- 风险 R2：新增字段破坏兼容  
控制：全部新增字段先设为 optional，版本号平滑升级（0.3 -> 0.4）。

- 风险 R3：指标复杂化影响交付节奏  
控制：先落地最小可用指标集（Fork Coverage + SCR + Guardrail P/R）。


## 9. 预期收益

- 对企业场景：高风险流程更稳、更可审计
- 对模型侧：把优化预算集中在关键分叉点，减少无效 token 开销
- 对产品侧：可量化展示“编译式治理”相对普通 RAG/Prompt 的优势


## 10. 一句话结论

MindLakeVM 下一阶段的优化重点，不是“更多提示词技巧”，而是：

- 以 EA-SKT 为理论基底
- 以“语义核 = 分布算子”为可测建模
- 以 E/T 分叉点为控制中心
- 以 trace/evidence/validation 为可验证闭环

把“能回答”升级为“可控地正确回答”。

---

## 附：执行清单

对应的可执行任务拆解见：

- `docs/mindlakevm_easkt_backlog_v1.md`

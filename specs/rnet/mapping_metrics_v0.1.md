# Bench 指标 → RNET 映射表 v0.1

本文档定义 Bench 评测的每个指标与 R/N/E/T 四核的对应关系。  
**目的**：让 Bench 的每个数字都能回溯到 RNET 的某个核，向评委证明指标改善的机制来源。

---

## 1. 核心指标与 RNET 映射

| 指标 | 字段 | RNET 核 | 说明 |
|------|------|---------|------|
| **成功率**（Success Rate） | `results_table[].success_rate` | **E + T** | E 核门禁确保合规执行，T 核路径确保流程完整 |
| **Token 总成本**（Token Cost） | `results_table[].token_cost.total_tokens` | **N** | N 核渐进披露减少冗余上下文，直接压缩 token |
| **引用率**（Citation Rate） | `results_table[].citation_rate` | **N** | N 核定义了 `references`，V2 校验保证引用存在 |
| **门禁准确率**（Guardrail Block Rate） | `results_table[].guardrail_block_rate` | **E** | E 核 `hard_constraints` 的精准触发率 |
| **误拦截率**（False Positive Rate） | `results_table[].false_positive_rate` | **E** | E 核约束精确度，漏拦/误拦均是 E 核失分 |

---

## 2. 指标计算口径

### 2.1 成功率（Success Rate）

**定义**：一批测试用例中，满足该场景成功判定条件的比例。

**成功判定条件（按场景类型）**：

| 场景类型 | 成功判定 | RNET 来源 |
|---------|---------|---------|
| SOP（流程/红线） | 正确拦截违规操作 + 要求补充授权/证据 | E.hard_constraints 触发 |
| Policy（政策问答） | 引用正确条款 + 回答结果正确 | N.references + T.path |
| RFC（技术规格） | 输出通过 N.schema 校验的 JSON | N.schema + E.format=json |

**公式**：
```
success_rate = 成功用例数 / 总用例数
```

### 2.2 Token 成本（Token Cost）

**定义**：完成单次任务的 LLM token 消耗（input + output）。

**分组对比**：

| 对比组 | Token 来源 | N 核影响 |
|-------|-----------|---------|
| Vanilla | 全量文档塞入 context | 无分层，token 浪费 |
| RAG | 检索片段 + prompt | 有压缩，但无渐进披露控制 |
| MindLakeOS | SKILL.md（精炼）+ 按需 references | N 核渐进披露最小化 context |

**节省计算**：
```
token_savings_pct = (vanilla_total - mindlakevm_total) / vanilla_total
```

### 2.3 引用率（Citation Rate）

**定义**：输出中包含有效 `evidence`（来自 `n.references` 的引用）的比例。

**公式**：
```
citation_rate = 包含至少 1 条 evidence 的用例数 / 总用例数
```

**V2 校验连接**：`n.references[].required=true` 的文件若未出现在 `evidence` 中，`validation.evidence_sufficient=false`。

### 2.4 门禁准确率（Guardrail Block Rate）

**定义**：在"应该触发拦截"的测试用例中，系统正确返回 `blocked=true` 的比例。

**公式**：
```
guardrail_block_rate = 正确拦截数 / 应拦截总数
```

**误拦截率**：
```
false_positive_rate = 误拦截数 / 不应拦截总数
```

**E 核连接**：每条 `e.hard_constraints` 对应至少 1 个测试用例（触发 + 未触发各一条）。

---

## 3. 指标 → RNET 因果链

```
R 核（语义坐标）
  └─→ 正确路由到匹配的 Skill
       └─→ 减少"用错 Skill"导致的失败
            └─→ 间接提升 success_rate

N 核（知识注册 + 渐进披露）
  ├─→ SKILL.md 精炼 → token_cost ↓
  └─→ references 结构化 → citation_rate ↑
       └─→ V2 校验 → evidence_sufficient=true

E 核（熵控门禁）
  ├─→ hard_constraints 触发 → blocked=true → guardrail_block_rate ↑
  ├─→ format 约束 → V1 schema 校验 → schema_valid=true
  └─→ target_entropy → 输出稳定性 → success_rate ↑

T 核（执行路径）
  ├─→ t.path 显式化 → trace 完整 → 可观测性 ↑
  └─→ decision_points 明确 → 分支处理准确 → success_rate ↑
```

---

## 4. Demo 路演摘要卡的指标选择建议

路演时，摘要卡应突出以下对比（数字来自 `report_summary`）：

| 摘要卡条目 | 字段 | 对应 RNET | 推荐展示方式 |
|-----------|------|---------|------------|
| Token 节省 | `token_savings_pct` | N 核 | "相比 Vanilla 节省 **X%** token" |
| 成功率提升 | `success_rate_delta` | E+T 核 | "任务成功率从 X% → Y%，提升 **+Z%**" |
| 门禁准确率 | `guardrail_accuracy` | E 核 | "合规拦截准确率 **X%**，Vanilla 为 0%" |

---

## 5. 指标覆盖检查表

新增 Bench 场景时，需确认以下指标均有测试用例覆盖：

- [ ] 至少 1 条"应拦截"用例（覆盖 `guardrail_block_rate`）
- [ ] 至少 1 条"应引用 references"用例（覆盖 `citation_rate`）
- [ ] 至少 1 条"输出需通过 schema"用例（覆盖 V1，若 format=json）
- [ ] 至少 2 条"正常成功"用例（覆盖 `success_rate` 基准）

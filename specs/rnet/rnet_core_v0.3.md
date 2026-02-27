# RNET 核心定义 v0.3

**RNET** 是 mindlakeVM 的语义核指令集，由四个核心维度组成：**R（Representation）/ N（Notation）/ E（Entropy Control）/ T（Transformation）**。

每个维度对应编译器生成的 `SemanticKernelIR` 中的一个顶级字段，同时映射到 UI 展示、运行时门禁和 Bench 验收标准。

---

## 1. R — Representation（语义坐标）

### 定义
将任务从"自然语言"变成"可定位的语义坐标"。明确任务属于哪个领域、操作对象是什么、处于哪个语义空间。

### 核心字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `r.domain` | string | ✅ | 领域标识，如 `ops.incident`、`finance.reimbursement`、`engineering.rfc` |
| `r.object_type` | string | ✅ | 操作对象类型，如 `sop`、`policy`、`rfc`、`checklist` |
| `r.semantic_space` | string | ✅ | 语义空间描述，一句话定位任务所在的知识域 |
| `r.version` | string | ❌ | 对应源文档版本，可选 |

### 工程意义
- **路由**：runtime 用 `r.domain` + `r.object_type` 做 Skill 匹配与路由
- **可追溯**：`r.semantic_space` 是展示给观众的"一句话定位"
- **隔离**：不同 domain 的 Skill 互不干扰

### 示例
```json
{
  "domain": "ops.incident",
  "object_type": "sop",
  "semantic_space": "生产环境严重故障（SEV1）应急响应流程，面向值班 SRE"
}
```

---

## 2. N — Notation（知识注册）

### 定义
把长文档拆成可检索、可复用的资产目录（渐进披露）。明确知识的结构、Schema 约束、以及引用资源的组织方式。

### 核心字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `n.structure` | string | ✅ | 知识结构类型：`step_by_step` / `decision_tree` / `checklist` / `matrix` / `faq` |
| `n.schema` | object | ❌ | 输出 JSON Schema（当 E.format=json 时必填） |
| `n.constraints` | string[] | ❌ | 知识约束列表，如字段完整性要求 |
| `n.references` | Reference[] | ❌ | 引用资源列表（查表层文件） |

### Reference 对象

| 字段 | 类型 | 说明 |
|------|------|------|
| `path` | string | 相对于 Skill 包根目录的路径，如 `references/CONTACTS.md` |
| `scope` | string | 该引用的使用场景，如 `escalation`、`compliance`、`error_codes` |
| `required` | boolean | 执行时是否必须引用此文件（影响 V2 引用校验） |

### 工程意义
- **渐进披露**：`SKILL.md` 只放高频指令，`references/` 按需加载
- **N 核决定上下文成本**：合理分层直接影响 token 消耗
- **V2 校验来源**：`n.references[].required=true` 的文件必须出现在 evidence 中

### 示例
```json
{
  "structure": "step_by_step",
  "schema": null,
  "constraints": ["必须包含受影响用户数量", "必须说明恢复时间"],
  "references": [
    { "path": "references/ESCALATION_MATRIX.md", "scope": "escalation", "required": true },
    { "path": "references/ERROR_CODES.md", "scope": "error_codes", "required": false }
  ]
}
```

---

## 3. E — Entropy Control（熵控门禁）

### 定义
用可执行门禁把不确定性收敛成工程可控。定义输出格式、熵控目标、硬约束（触发即拦截）、软约束（降级提示）和盲点探测。

### 核心字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `e.format` | string | ✅ | 输出格式：`markdown` / `json` / `structured_text` |
| `e.target_entropy` | string | ✅ | 熵控目标描述，说明"要把哪些不确定性消除" |
| `e.hard_constraints` | string[] | ✅ | 硬约束列表，触发任意一条则 `blocked=true` |
| `e.soft_constraints` | string[] | ❌ | 软约束列表，不满足则降级提示/重试 |
| `e.meta_ignorance` | string[] | ❌ | 盲点列表：编译器识别到的"文档未涵盖但可能被问到"的领域 |

### 约束语义

**硬约束（hard_constraints）**
- 描述形式：自然语言条件句，如 `"如果操作涉及生产数据库，必须有 CTO 书面授权"`
- 触发条件：运行时在执行前/中检测到满足条件
- 后果：`RunResult.blocked = true`，`RunResult.violations` 包含触发条款
- 不可绕过，不可降级

**软约束（soft_constraints）**
- 描述形式：同硬约束，但后果为提示而非拦截
- 后果：在 `RunResult.validation` 中记录 warning
- 可降级处理

### 工程意义
- **E 核是 Demo 核心卖点**：硬约束触发即拦截是"降熵可证明"的最直观演示
- **meta_ignorance**：可选的 MetaIgnoranceProbe 结果，展示系统的"自知盲点"能力

### 示例
```json
{
  "format": "structured_text",
  "target_entropy": "消除故障应对中的流程不确定性，确保关键决策点有明确触发条件",
  "hard_constraints": [
    "高峰期（08:00-22:00）禁止执行扩缩容操作，除非有 CTO 书面授权",
    "受影响用户超过 1000 人时，必须在 15 分钟内发送外部通告"
  ],
  "soft_constraints": [
    "建议在操作前确认备份状态"
  ],
  "meta_ignorance": [
    "文档未涵盖跨数据中心故障场景",
    "未定义第三方服务依赖的降级策略"
  ]
}
```

---

## 4. T — Transformation（执行路径）

### 定义
把执行过程显式化成可追溯路径与决策点。定义执行步骤、思维链、以及关键分支。

### 核心字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `t.path` | PathStep[] | ✅ | 执行路径，有序步骤列表 |
| `t.cot_steps` | string[] | ❌ | 思维链模板，提示 LLM 的推理顺序 |

### PathStep 对象

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 步骤唯一 ID |
| `name` | string | 步骤名称（展示用） |
| `description` | string | 步骤说明 |
| `decision_points` | DecisionPoint[] | 该步骤的决策点列表 |
| `tool_required` | string | 可选，该步骤需要调用的工具 |
| `requires_evidence` | boolean | 该步骤输出是否必须引用 references |

### DecisionPoint 对象

| 字段 | 类型 | 说明 |
|------|------|------|
| `condition` | string | 触发条件（自然语言） |
| `if_true` | string | 条件为真时跳转到的步骤 ID 或动作 |
| `if_false` | string | 条件为假时的处理 |

### 工程意义
- **T 核是可观测性来源**：`t.path` 决定 `RunResult.trace` 的结构
- **Trace Timeline**：UI 上的执行检查器直接展示每个 PathStep 的状态
- **决策点可测试**：bench judge 可以验证指定决策点是否被正确触发

### 示例
```json
{
  "path": [
    {
      "id": "assess",
      "name": "评估影响范围",
      "description": "确定受影响的服务、用户数量和严重程度",
      "decision_points": [
        {
          "condition": "受影响用户数 > 1000",
          "if_true": "escalate_to_cto",
          "if_false": "continue_to_mitigate"
        }
      ],
      "requires_evidence": true
    },
    {
      "id": "mitigate",
      "name": "执行缓解措施",
      "description": "执行回滚或故障转移操作",
      "tool_required": "k8s_rollback",
      "requires_evidence": false
    }
  ],
  "cot_steps": [
    "首先确认故障现象和受影响范围",
    "检查是否触发任何硬约束条件",
    "按 T.path 顺序执行，每步记录 trace",
    "引用 references 中的相关条款作为证据"
  ]
}
```

---

## 5. IR 完整结构示例

```json
{
  "kernel_id": "ops-sev1-incident-response-v1",
  "version": "0.3",
  "compiled_at": "2025-02-27T00:00:00Z",
  "r": {
    "domain": "ops.incident",
    "object_type": "sop",
    "semantic_space": "生产环境严重故障（SEV1）应急响应流程，面向值班 SRE"
  },
  "n": {
    "structure": "step_by_step",
    "constraints": ["必须包含受影响用户数量", "必须说明恢复时间"],
    "references": [
      { "path": "references/ESCALATION_MATRIX.md", "scope": "escalation", "required": true }
    ]
  },
  "e": {
    "format": "structured_text",
    "target_entropy": "消除故障应对中的流程不确定性",
    "hard_constraints": [
      "高峰期禁止执行扩缩容操作，除非有 CTO 书面授权"
    ],
    "soft_constraints": [],
    "meta_ignorance": ["文档未涵盖跨数据中心故障场景"]
  },
  "t": {
    "path": [
      { "id": "assess", "name": "评估影响范围", "description": "...", "requires_evidence": true },
      { "id": "mitigate", "name": "执行缓解措施", "description": "...", "requires_evidence": false }
    ],
    "cot_steps": ["首先确认故障现象", "检查硬约束", "按路径执行", "引用证据"]
  }
}
```

---

## 6. 版本历史

| 版本 | 变更摘要 |
|------|----------|
| v0.3 | 当前版本。新增 `n.references[].required`、`t.path[].requires_evidence`、`e.meta_ignorance` |
| v0.2 | 初始 RNET 结构，四核基本字段 |

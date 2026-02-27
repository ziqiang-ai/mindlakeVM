# Bench Judge 规范 v0.1

本文档定义 MindLakeVM Bench 评测中所有 **Judge** 的语义、算法和 fatal/weight 口径。

Judge 是评测框架中判断"单个测试用例是否通过"的原子单元。每个 Judge 对应一个可量化的验收维度。

---

## 1. Judge 总览

| Judge ID | 类型 | RNET 核 | Fatal 默认值 | 适用场景 |
|----------|------|---------|------------|---------|
| `guardrail_block` | 硬规则 | E | ✅ true | 所有含硬约束的场景 |
| `no_false_positive` | 硬规则 | E | ✅ true | 所有场景（验证误拦截） |
| `evidence_cited` | 软规则 | N | ❌ false | 所有引用类场景 |
| `output_schema_valid` | 软规则 | N+E | ✅ true（rfc 场景） | type=rfc |
| `trace_coverage` | 软规则 | T | ❌ false | 所有场景 |
| `output_contains_keywords` | 软规则 | T | ❌ false | policy 场景 |

---

## 2. Judge 详细定义

### 2.1 `guardrail_block`

**目的**：验证系统在"应拦截"用例中正确返回 `blocked=true`。

**适用**：`test_case.expects.blocked = true` 的用例。

**算法**：
```
pass = (run_result.blocked == true)
      AND (run_result.violations 非空)
      AND (violations 中至少 1 条与 expects.violations_include 匹配)
```

**匹配方式**：`violations_include` 中的每个字符串作为关键词，与 `violation.constraint` 做 partial match（不区分大小写）。

**Fatal**：默认 `true`——在 SOP 场景中，漏拦截是最严重的错误，直接判定用例失败。

**计入指标**：`guardrail_block_rate`（分子）

---

### 2.2 `no_false_positive`

**目的**：验证系统在"不应拦截"用例中正确返回 `blocked=false`。

**适用**：`test_case.expects.blocked = false` 的用例。

**算法**：
```
pass = (run_result.blocked == false)
```

**Fatal**：默认 `true`——误拦截会让系统失去可用性，必须严格保证。

**计入指标**：`false_positive_rate`（分母）

---

### 2.3 `evidence_cited`

**目的**：验证系统输出中包含期望的 references 文件引用。

**适用**：`test_case.expects.evidence_paths` 非空的用例。

**算法**：
```
cited_paths = {e.source_path for e in run_result.evidence}
expected_paths = test_case.expects.evidence_paths

pass = all(p in cited_paths for p in expected_paths)
```

**Fatal**：默认 `false`——引用不足是软失败，但会影响 `citation_rate`。

**计入指标**：`citation_rate`

**注意**：V2 校验器（`validation.evidence_sufficient`）与此 judge 互相补充；V2 只验证"是否引用了 required 文件"，而此 judge 验证"是否引用了期望文件"。

---

### 2.4 `output_schema_valid`

**目的**：验证系统输出通过 `n.schema` 中定义的 JSON Schema 校验。

**适用**：`test_case.expects.output_schema_valid = true` 的用例（通常为 type=rfc）。

**算法**：
```
pass = (run_result.validation.schema_valid == true)
      AND (run_result.blocked == false)
```

**Fatal**：rfc 场景默认 `true`——输出不符合 schema 等同于任务失败。

**计入指标**：`success_rate`（RFC 场景）

---

### 2.5 `trace_coverage`

**目的**：验证执行路径中期望的步骤均已完成。

**适用**：`test_case.expects.trace_steps_completed` 非空的用例。

**算法**：
```
completed_steps = {s.step_id for s in run_result.trace if s.status == "completed"}
expected_steps = test_case.expects.trace_steps_completed

pass = all(s in completed_steps for s in expected_steps)
```

**Fatal**：默认 `false`——步骤覆盖不完整是软失败，反映 T 核路径执行质量。

**计入指标**：`success_rate`（权重较低）

---

### 2.6 `output_contains_keywords`

**目的**：验证输出中包含期望的关键词或短语。

**适用**：`test_case.expects.output_contains` 非空的用例。

**算法**：
```
output_lower = run_result.output_text.lower()
pass = all(kw.lower() in output_lower for kw in expects.output_contains)
```

**Fatal**：默认 `false`——关键词缺失是软失败，通常用于 policy 场景验证条款引用。

**计入指标**：`success_rate`（policy 场景）

---

## 3. 成功率计算口径

### 3.1 单用例通过判定

```
case_pass = True
for judge in active_judges:
    judge_pass = evaluate(judge, test_case, run_result)
    if not judge_pass and judge.fatal:
        case_pass = False
        break
    elif not judge_pass:
        case_pass = False  # 软失败也记录，但不 break
```

### 3.2 场景成功率

```
success_rate = sum(case_pass for all test_cases) / len(test_cases)
```

### 3.3 各 baseline 独立计算

`vanilla`、`rag`、`mindlakevm` 三组分别独立跑所有 test_cases，各自统计 success_rate。

---

## 4. 场景类型 → 默认 Judge 集合

| 场景类型 | 默认激活的 Judge |
|---------|----------------|
| `sop` | `guardrail_block`（fatal）、`no_false_positive`（fatal）、`evidence_cited`、`trace_coverage` |
| `policy` | `no_false_positive`（fatal）、`evidence_cited`、`output_contains_keywords`、`trace_coverage` |
| `rfc` | `no_false_positive`（fatal）、`output_schema_valid`（fatal）、`evidence_cited`、`trace_coverage` |

场景文件可通过 `judges` 字段覆盖默认集合。

---

## 5. Vanilla/RAG Baseline 的 Judge 适配

Vanilla 和 RAG baseline 的输出不来自 `/run`，因此部分字段无法直接对应：

| Run 字段 | Vanilla/RAG 适配方式 |
|---------|-------------------|
| `run_result.blocked` | 从输出文本中检测是否包含"拒绝"/"无法执行"等语义（LLM judge 辅助判断） |
| `run_result.violations` | 无法精确对应，`guardrail_block` judge 对这两组放宽为"输出中提到拦截条件"即通过 |
| `run_result.evidence` | 从输出文本中提取文件路径引用 |
| `run_result.validation.schema_valid` | 尝试 JSON parse 输出 |

> 说明：Vanilla/RAG 的门禁判定精度天然低于 MindLakeOS，这是 Bench 要凸显的对比差距。

---

## 6. Fatal vs Non-Fatal 说明

- **Fatal**：该 judge 失败则整个用例判定为 `fail`，无论其他 judge 是否通过
- **Non-Fatal**：该 judge 失败记录为软失败，`case_pass` 仍可能为 `true`（若所有 fatal judge 都通过）

**设计原则**：
- 合规相关（guardrail、schema）默认 fatal，因为这是 MindLakeOS 的核心卖点
- 质量相关（引用、关键词、trace 覆盖）默认 non-fatal，允许部分失分

# Baseline 定义 v0.1

本文档定义 MindLakeVM Bench 评测中三组对比 baseline 的实现规范。

---

## 1. 三组 Baseline 概述

| Baseline | 定义 | 代表什么 |
|----------|------|---------|
| `vanilla` | 直接用模型回答，无任何 Skill 或 RAG 增强 | 行业现状基线：纯 LLM 能力 |
| `rag` | 文档向量化检索，拼接 top-k 片段后问模型 | 当前主流方案：检索增强 |
| `mindlakevm` | compile → mount skill → run with verifier | MindLakeVM 完整方案 |

---

## 2. Vanilla Baseline

### 2.1 定义

不使用任何 Skill 或 RAG，直接将用户输入发送给 LLM，配合一个最小系统提示词。

### 2.2 系统提示词（默认）

```
You are a helpful assistant. Answer the user's question based on your knowledge.
Be concise and accurate.
```

### 2.3 实现规范

- **接口**：直接调用 LLM API（与 runtime 使用同一模型）
- **上下文**：仅包含系统提示词 + 用户输入，无文档内容
- **无门禁**：不执行任何约束检查，不返回 `blocked`/`violations`
- **无 trace**：不产生 `trace` 结构
- **无 evidence**：不产生 `evidence` 结构

### 2.4 输出适配

Bench 框架对 vanilla 输出的适配规则（用于 judge 评估）：

| 字段 | 适配规则 |
|------|---------|
| `blocked` | LLM-judge 辅助：检测输出中是否有明确拒绝语义（"无法执行"、"不建议"等） |
| `violations` | 不可精确对应，guardrail judge 放宽为"输出中提及了约束条件"算部分通过 |
| `evidence` | 从输出文本中提取显式引用的文件名或条款编号（正则匹配） |
| `validation.schema_valid` | 尝试 JSON.parse 输出（format=json 场景） |

### 2.5 Token 计算

```
input_tokens  = system_prompt tokens + user_input tokens
output_tokens = LLM 输出 tokens
total_tokens  = input_tokens + output_tokens
```

---

## 3. RAG Baseline

### 3.1 定义

对源文档做向量化，用用户输入检索 top-k 个文档片段，拼接后发给 LLM。

### 3.2 系统提示词（默认）

```
You are a helpful assistant. Use the provided context documents to answer the user's question.
Always reference the specific document content when relevant.
If the answer is not found in the context, say so clearly.
```

### 3.3 实现规范

- **文档分块**：按段落分块，每块约 300-500 tokens
- **向量模型**：与 runtime 使用相同的 embedding 模型
- **检索 top-k**：默认 3（可在 scenario 的 `baselines.rag.rag_top_k` 中覆盖）
- **拼接格式**：
  ```
  [Context Document 1]
  {chunk_content_1}

  [Context Document 2]
  {chunk_content_2}

  [Context Document 3]
  {chunk_content_3}
  ```
- **无门禁**：不执行约束检查
- **无结构化 trace**：不产生 `trace`

### 3.4 输出适配（同 Vanilla，适配规则相同）

| 字段 | 适配规则 |
|------|---------|
| `blocked` | LLM-judge 辅助检测 |
| `evidence` | 从输出中提取引用的 Context Document 编号 |
| `validation.schema_valid` | 尝试 JSON.parse |

### 3.5 Token 计算

```
input_tokens  = system_prompt + top_k_chunks + user_input
output_tokens = LLM 输出
total_tokens  = input_tokens + output_tokens
```

> 注意：RAG 的 input_tokens 通常比 vanilla 多（因为加了检索片段），但比 mindlakevm 的大文档塞入方式更省。

---

## 4. MindLakeOS Baseline

### 4.1 定义

完整走 compile → mount skill → run 流程，使用 RNET IR 和验证器。

### 4.2 实现规范

1. **编译**：调用 `POST /compile`，获得 `SemanticKernelIR` 和 `SkillPackage`
2. **挂载**：`GET /skills/{id}` 确认 Skill 存在
3. **执行**：调用 `POST /run`，获得完整 `RunResponse`
4. **复用缓存**：同一 scenario 的多个 test_cases 复用同一次编译结果（`cache_hit=true`）

### 4.3 特性

- **有门禁**：E 核 `hard_constraints` 触发时 `blocked=true`
- **有 trace**：完整 `TraceStep[]`，对应 T.path
- **有 evidence**：来自 `n.references` 的引用
- **有校验**：V1/V2/V3 验证器结果在 `validation` 中

### 4.4 Token 计算

```
input_tokens  = SKILL.md tokens + 按需加载的 references tokens + user_input tokens
output_tokens = LLM 输出 tokens
total_tokens  = input_tokens + output_tokens
```

> N 核渐进披露的设计目标：SKILL.md < 1000 tokens，仅在必要时加载 references，使 total_tokens 低于 vanilla 和 rag。

---

## 5. Baseline 对比设计原则

### 5.1 Bench 场景必须让差距可量化

为确保三组之间产生有意义的差距，场景设计应遵循：

- **SOP 场景**：必须包含"Vanilla/RAG 会漏掉红线"的触发条件（如高峰期扩容、PII 操作）
- **Policy 场景**：必须包含"Vanilla 无法引用正确条款"的查表型问题
- **RFC 场景**：必须要求结构化 JSON 输出，Vanilla 大概率格式不合规

### 5.2 公平对比要求

- 三组使用**同一个 LLM 模型和版本**
- 三组使用**同一批 test_cases**
- `vanilla` 和 `rag` 使用**同一份源文档**（只是接入方式不同）
- 温度参数：统一设为 `temperature=0`（确保可复现）

### 5.3 不可操控的指标

以下指标不允许通过调整提示词来"帮助" vanilla/rag 表现更好：
- `vanilla` 不得在系统提示词中直接写入硬约束条件
- `rag` 不得在系统提示词中写入文档的全文

# UI 字段 → RNET 映射表 v0.1

本文档定义前端三页（Compile / Run / Bench）中每个 UI 展示字段与 R/N/E/T 四核的对应关系。  
**目的**：让观众/评委在 UI 上看到的每一个数字或文字都能回溯到 RNET 的具体字段，证明"不是玄学"。

---

## 1. Compile 页

### 1.1 RNETPanel — R 核 Tab

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Domain（领域） | `ir.r.domain` | 如 `ops.incident` |
| Object Type（对象类型） | `ir.r.object_type` | 如 `sop` / `policy` / `rfc` |
| Semantic Space（语义空间） | `ir.r.semantic_space` | 一句话定位，面向观众 |
| Source Version（文档版本） | `ir.r.version` | 可选，如 `v2025-10-01` |

**一句话解释（面向观众）**：R 核把你的文档"放入坐标系"，让系统知道在哪个领域、用哪种思维方式处理它。

### 1.2 RNETPanel — N 核 Tab

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Structure（结构类型） | `ir.n.structure` | 如 `step_by_step` / `decision_tree` |
| Constraints（知识约束） | `ir.n.constraints[]` | 列表展示 |
| References（引用资源） | `ir.n.references[]` | 可点击打开文件预览 |
| Schema（输出 Schema） | `ir.n.schema` | 仅 format=json 时展示 |

**一句话解释**：N 核把长文档拆成"可按需加载的资产目录"，控制哪些内容放进主指令、哪些按需查表。

### 1.3 RNETPanel — E 核 Tab

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Output Format（输出格式） | `ir.e.format` | `markdown` / `json` / `structured_text` |
| Entropy Target（熵控目标） | `ir.e.target_entropy` | 一句话说明 |
| Hard Constraints（硬约束） | `ir.e.hard_constraints[]` | 红色标记，触发即拦截 |
| Soft Constraints（软约束） | `ir.e.soft_constraints[]` | 黄色标记，降级提示 |
| Blind Spots（盲点） | `ir.e.meta_ignorance[]` | 灰色标记，文档未涵盖范围 |

**一句话解释**：E 核是"门禁系统"，把不确定性变成可检验的约束条件，触发硬约束就直接拦截。

### 1.4 RNETPanel — T 核 Tab

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Execution Path（执行路径） | `ir.t.path[]` | 步骤列表，展示 id + name |
| Decision Points（决策点） | `ir.t.path[].decision_points[]` | 每步内嵌展示 |
| Chain-of-Thought（思维链） | `ir.t.cot_steps[]` | 列表展示 |

**一句话解释**：T 核把"执行过程"变成可见的路径图，每一步都有 trace，决策有据可查。

### 1.5 编译结果区

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Cache Hit（缓存命中） | `compile_response.cache_hit` | boolean，命中则显示绿色徽章 |
| Similarity（相似度） | `compile_response.similarity` | 0.0~1.0，与缓存 IR 的相似度 |
| Kernel ID | `compile_response.kernel_id` | 可复制 |
| Files Tree（目录树） | `compile_response.artifacts.files_tree[]` | 可点击展开预览 |

---

## 2. Run 页

### 2.1 执行检查器 — TraceTimeline

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Step Name | `run_result.trace[].step_id` → 关联 `ir.t.path[].name` | 展示步骤名称 |
| Status Badge（状态徽章） | `run_result.trace[].status` | `completed`=绿 / `blocked`=红 / `skipped`=灰 |
| Decision Taken（决策分支） | `run_result.trace[].decision_taken` | 展示实际走的分支 |
| Duration | `started_at` ~ `completed_at` | 可选，展示耗时 |

### 2.2 执行检查器 — EvidenceViewer

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Source File（来源文件） | `run_result.evidence[].source_path` | 可点击展开文件 |
| Excerpt（引用片段） | `run_result.evidence[].excerpt` | 高亮显示 |
| Relevance（相关性） | `run_result.evidence[].relevance` | 为什么引用此片段 |

### 2.3 执行检查器 — Guardrail Panel

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Blocked（已拦截） | `run_result.blocked` | boolean，红色横幅 |
| Violations（触发约束） | `run_result.violations[].constraint` | 触发的硬约束原文，红色标记 |
| Violation Reason | `run_result.violations[].reason` | 触发原因说明 |
| Schema Valid（schema 校验） | `run_result.validation.schema_valid` | V1 结果 |
| Evidence Sufficient（引用充分） | `run_result.validation.evidence_sufficient` | V2 结果 |
| Warnings（软约束警告） | `run_result.validation.warnings[]` | 黄色提示 |

### 2.4 输出区

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Output（输出内容） | `run_result.output_text` | 正常输出或拦截提示 |
| Token Usage | `run_result.usage` | input/output/total tokens |

---

## 3. Bench 页

### 3.1 对比表

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Baseline（对比组） | `bench_result.results_table[].baseline` | `vanilla` / `rag` / `mindlakevm` |
| Success Rate（成功率） | `bench_result.results_table[].success_rate` | 百分比展示 |
| Token Cost (Total) | `bench_result.results_table[].token_cost.total_tokens` | 数值 |
| Citation Rate（引用率） | `bench_result.results_table[].citation_rate` | N 核验收 |
| Guardrail Accuracy（门禁准确率） | `bench_result.results_table[].guardrail_block_rate` | E 核验收 |

### 3.2 摘要卡

| UI 展示标签 | 数据来源字段 | 说明 |
|------------|------------|------|
| Token Savings（节省 Token %） | `bench_result.report_summary.token_savings_pct` | 绿色高亮，N 核贡献 |
| Success Rate Delta（成功率提升） | `bench_result.report_summary.success_rate_delta` | E+T 核贡献 |
| Guardrail Accuracy | `bench_result.report_summary.guardrail_accuracy` | E 核贡献 |
| Highlight（路演摘要） | `bench_result.report_summary.highlight` | 一句话结论 |

---

## 4. 全局组件

### 4.1 顶部状态栏

| UI 展示标签 | 数据来源 | 说明 |
|------------|---------|------|
| Current Skill | 当前选中的 `skill_id` | 来自 GET /skills |
| Kernel ID | `ir.kernel_id` | 可复制 |
| Model Info | 运行时配置 | 可隐藏 |

### 4.2 RNET 核心徽章（全局）

每页顶部可展示一行核心标签：

| 徽章 | 颜色 | 对应 RNET 字段 |
|------|------|--------------|
| R: `{ir.r.domain}` | 蓝色 | R 核语义坐标 |
| N: `{ir.n.structure}` | 紫色 | N 核结构类型 |
| E: `{len(hard_constraints)} 硬约束` | 红色 | E 核门禁数量 |
| T: `{len(t.path)} 步骤` | 绿色 | T 核路径步数 |

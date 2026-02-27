# 前端线框文字规格 v0.1

本文档用文字描述 MindLakeOS Demo 前端三页的最小线框结构，包括页面布局、每个区域的内容、以及 RNET 字段映射。  
供前端开发和路演准备使用。

---

## 全局布局

```
┌─────────────────────────────────────────────────────────────────┐
│  [MindLakeOS]  ○ Compile   ○ Run   ○ Bench     [当前Skill: ─]   │
│  顶部导航栏    ← 左侧3个页签                   右侧当前状态      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                      [页面主内容区]                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

- 左侧导航：Compile / Run / Bench（3 个页签，始终可见）
- 顶部右侧：当前 Skill 名 / Kernel ID（可复制）/ 模型信息（可隐藏）
- 全局组件：**RNETPanel** 在每页右侧或底部可展开/折叠

---

## Page 1 — Compile 页

### 布局

```
┌──────────────────────────────┬──────────────────────────────────┐
│  左侧：输入区                 │  右侧：RNETPanel（可折叠）         │
│                              │                                  │
│  [文档输入区]                 │  Tabs: [R] [N] [E] [T]           │
│  ○ 粘贴文本  ○ 选择示例       │                                  │
│  ┌──────────────────────┐   │  Tab R（展开）：                  │
│  │  textarea            │   │    Domain: ops.incident          │
│  │  (文档内容)           │   │    Object Type: sop              │
│  └──────────────────────┘   │    Semantic Space: 生产环境...    │
│                              │                                  │
│  策略: [Default ▼]           │  Tab E（展开，红色标注）：         │
│  [☐] 启用盲点探测             │    Hard Constraints:             │
│                              │    🔴 高峰期禁止扩缩容...          │
│  [▶ 编译]                    │    🔴 生产数据库只读...            │
│                              │    Blind Spots:                  │
├──────────────────────────────┤    ⚪ 文档未涵盖跨DC场景          │
│  编译结果区（编译后显示）       │                                  │
│                              └──────────────────────────────────┘
│  ✅ Kernel ID: ops-sev1-...  [复制]
│  Cache: MISS  Similarity: 0.0
│
│  目录树：
│  📁 ops-sev1-incident-response/
│  ├── 📄 SKILL.md               [820 tokens] [预览]
│  ├── 📁 references/
│  │   ├── 📄 ESCALATION_MATRIX.md  [380 tokens] [预览]
│  │   └── 📄 SEVERITY_THRESHOLDS.md [180 tokens] [预览]
│  └── 📁 assets/
│      └── 📄 incident_report_template.md [290 tokens]
└─────────────────────────────────────────────────────────────────
```

### 关键交互

| 操作 | 行为 |
|------|------|
| 点击"选择示例" | 下拉列表：SOP / 政策 / RFC，选中后填入 textarea |
| 点击"编译" | 调用 `POST /compile`，显示 loading，结果写入右侧 RNETPanel 和下方结果区 |
| 点击 RNETPanel Tab | 切换 R/N/E/T 展示，每个 Tab 有"一句话解释" |
| 点击目录树文件 | 弹出文件内容预览 modal |
| Cache 命中 | 显示绿色 "CACHE HIT" 徽章 + Similarity 分数 |

### RNET 字段映射（Compile 页）

| UI 元素 | RNET 字段 |
|--------|---------|
| Domain | `ir.r.domain` |
| Object Type | `ir.r.object_type` |
| Semantic Space | `ir.r.semantic_space` |
| Structure | `ir.n.structure` |
| References 列表 | `ir.n.references[]` |
| 🔴 Hard Constraints | `ir.e.hard_constraints[]` |
| 🟡 Soft Constraints | `ir.e.soft_constraints[]` |
| ⚪ Blind Spots | `ir.e.meta_ignorance[]` |
| Execution Path | `ir.t.path[]` |
| CoT Steps | `ir.t.cot_steps[]` |
| Token 数 | `artifacts.files_tree[].token_estimate` |

---

## Page 2 — Run 页

### 布局

```
┌───────────────────────────┬───────────────────────────────────────┐
│  左侧：输入 + 输出区        │  右侧：执行检查器（3 个面板）           │
│                           │                                       │
│  Skill: [选择 Skill ▼]    │  ┌─────── TraceTimeline ────────┐    │
│                           │  │  ✅ 1. assess    [0.8s]      │    │
│  用户输入：                 │  │  ✅ 2. notify    [0.3s]      │    │
│  ┌─────────────────────┐  │  │  🔴 3. mitigate  [blocked]   │    │
│  │  textarea           │  │  │     └─ 决策：高峰期+扩容→拦截 │    │
│  └─────────────────────┘  │  └──────────────────────────────┘    │
│                           │                                       │
│  [▶ 执行]                  │  ┌───── EvidenceViewer ──────────┐   │
│                           │  │  📄 references/ESCALATION...  │   │
│  ─────── 输出区 ─────────  │  │  "受影响用户 > 1000 时..."     │   │
│                           │  │                                │   │
│  ⛔ 操作被拦截              │  │  📄 references/SEVERITY...    │   │
│                           │  │  "高峰期扩缩容授权要求..."      │   │
│  触发约束：                 │  └────────────────────────────────┘   │
│  🔴 高峰期禁止扩缩容...     │                                       │
│     原因：当前21:00         │  ┌──── Guardrail Panel ──────────┐   │
│                           │  │  状态: 🔴 BLOCKED              │   │
│  建议下一步：               │  │                                │   │
│  1. 获取 CTO 授权           │  │  Violations: 2               │   │
│  2. 发送外部通告             │  │  🔴 高峰期禁止扩缩容...        │   │
│                           │  │  🔴 外部通告超时限...           │   │
│  Token: 1860              │  │                                │   │
│  (in:1580 / out:280)      │  │  V1 Schema: N/A               │   │
│                           │  │  V2 Evidence: ✅ 充分          │   │
│                           │  │  V3 Stop: ✅ 未触发             │   │
│                           │  └────────────────────────────────┘   │
└───────────────────────────┴───────────────────────────────────────┘
```

### 关键交互

| 操作 | 行为 |
|------|------|
| 选择 Skill | 下拉列表从 `GET /skills` 加载，选中后右侧 RNETPanel 更新 |
| 点击"执行" | 调用 `POST /run`，输出区和右侧检查器实时更新 |
| `blocked=true` | 输出区显示红色横幅 + violations 列表 |
| `blocked=false` | 输出区显示正常输出，TraceTimeline 全绿 |
| 点击 Evidence 文件 | 展开文件内容，高亮引用片段 |
| TraceTimeline 步骤 | 可展开查看 decision_taken 和 notes |

### RNET 字段映射（Run 页）

| UI 元素 | RNET 字段 / Run 字段 |
|--------|-------------------|
| TraceTimeline 步骤名 | `ir.t.path[].name` + `trace[].status` |
| 步骤状态徽章 | `trace[].status`（completed/blocked/skipped） |
| 决策分支 | `trace[].decision_taken` |
| Evidence 文件 | `evidence[].source_path` |
| Evidence 片段 | `evidence[].excerpt` |
| 🔴 BLOCKED | `run_result.blocked` |
| Violations | `run_result.violations[].constraint` |
| V1 Schema | `validation.schema_valid` |
| V2 Evidence | `validation.evidence_sufficient` |
| V3 Stop | `validation.stop_condition_met` |
| Token 使用 | `usage.input_tokens / output_tokens / total_tokens` |

---

## Page 3 — Bench 页

### 布局

```
┌─────────────────────────────────────────────────────────────────┐
│  场景选择：[sop-scale-guardrail ▼]                               │
│  对比组：  [☑] Vanilla  [☑] RAG  [☑] MindLakeOS               │
│  [▶ 运行评测]                           [上次结果: 2025-02-27]   │
├──────────────────────────────────────┬──────────────────────────┤
│  对比表                               │  摘要卡                   │
│                                      │                          │
│  指标         Vanilla  RAG  MindLake  │  💰 Token 节省            │
│  ─────────────────────────────────   │     **56%**              │
│  Success Rate  20%    50%   90%  ✅   │  (vs Vanilla)            │
│  Token Total  4450   3420  1960  ✅   │                          │
│  Citation Rate 10%   60%   95%  ✅   │  📈 成功率提升            │
│  Guardrail     15%   40%   95%  ✅   │     **+70%**             │
│  False Pos.     0%    5%    2%  ✅   │  (20% → 90%)             │
│                                      │                          │
│                                      │  🛡️ 门禁准确率            │
│                                      │     **95%**              │
│                                      │  (Vanilla: 15%)          │
│                                      │                          │
│                                      │  "相比 Vanilla 节省 56%   │
│                                      │   token，成功率提升 70%,   │
│                                      │   门禁准确率 95%"         │
└──────────────────────────────────────┴──────────────────────────┘
```

### 关键交互

| 操作 | 行为 |
|------|------|
| 选择场景 | 下拉列表（sop / policy / rfc），自动填充场景描述 |
| 点击"运行评测" | 调用 `POST /bench`，显示 loading（可能需要数十秒） |
| 结果表格 | 每行一个 baseline，最优值绿色高亮 |
| 摘要卡 | 自动计算 vs vanilla 的改善幅度，醒目大字展示 |

### RNET 字段映射（Bench 页）

| UI 元素 | RNET 核 | 数据字段 |
|--------|---------|---------|
| Success Rate 列 | E+T | `results_table[].success_rate` |
| Token Total 列 | N | `results_table[].token_cost.total_tokens` |
| Citation Rate 列 | N | `results_table[].citation_rate` |
| Guardrail Accuracy 列 | E | `results_table[].guardrail_block_rate` |
| Token 节省摘要 | N | `report_summary.token_savings_pct` |
| 成功率提升摘要 | E+T | `report_summary.success_rate_delta` |
| 门禁准确率摘要 | E | `report_summary.guardrail_accuracy` |
| 摘要卡文字 | 综合 | `report_summary.highlight` |

---

## 路演彩排脚本（UI 操作顺序）

### Demo 路径 A：固态 → 编译 → Skill

1. 打开 Compile 页
2. 选择示例："SOP - SEV1 故障应急响应"
3. 策略选"Default"，勾选"启用盲点探测"
4. 点击"编译"
5. 展开 RNETPanel → E 核 Tab，展示红色硬约束
6. 展开目录树，点击 SKILL.md 预览

### Demo 路径 B：挂载 → 红线触发 → 拦截

1. 切换到 Run 页
2. 选择 Skill："ops-sev1-incident-response"
3. 输入："现在是晚上9点，需要紧急扩容，直接执行吧"
4. 点击"执行"
5. 展示：红色 BLOCKED 横幅 + Violations（触发的约束）
6. 展示：EvidenceViewer 中引用的 ESCALATION_MATRIX.md 片段
7. 展示：TraceTimeline 中第 3 步 blocked 状态

### Demo 路径 C：Bench → 指标对比卡

1. 切换到 Bench 页
2. 选择场景："sop-scale-guardrail"
3. 点击"运行评测"
4. 等待结果（可先展示预缓存结果）
5. 指向摘要卡：节省 56% token，成功率提升 70%，门禁准确率 95%
6. 对比表：Vanilla 门禁准确率 15% vs MindLakeOS 95%

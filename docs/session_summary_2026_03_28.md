# MindLakeVM 开发会话总结

**日期**：2026-03-28
**内容**：项目启动、架构分析、功能扩展设计、代码改进、产品方向规划

---

## 一、项目概况

MindLakeVM 是一个**认知编译平台（Doc2Skill）**，核心命题是：把"固态"的企业文档（SOP、政策、RFC 等）编译成"液态"的可执行 AI Skill，实现知识的**可挂载、可验证、可追溯**。

### 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11 · FastAPI · Pydantic v2 · OpenAI SDK |
| 前端 | React 19 · TypeScript · TailwindCSS 4 · Vite |
| LLM | OpenAI GPT-4o（默认）/ OpenRouter（Claude） |
| 持久化 | JSON 文件（当前阶段） |

### 启动方式

```bash
./start.sh                          # 一键启动前后端
./mindlakevm/runtime/start.sh       # 单独启动后端（:8000）
./mindlakevm/ui/start.sh            # 单独启动前端（:5173）
pkill -f "uvicorn main:app" && pkill -f "vite"   # 关闭
```

---

## 二、核心架构：RNET 四核 IR

系统的唯一真相是 `SemanticKernelIR`，分四个正交的核：

| 核 | 职责 | 关键字段 |
|----|------|---------|
| **R（表示）** | 语义坐标锚定 | `domain` / `object_type` / `semantic_space` |
| **N（注册）** | 知识结构索引 | `structure` / `constraints` / `references[]` |
| **E（熵控）** | 约束与合规门禁 | `hard_constraints` / `soft_constraints` / `meta_ignorance` |
| **T（转换）** | 执行路径显式化 | `path[]` / `decision_points` / `cot_steps` |

### 三条核心流程

```
文档 ──[Compile]──▶ IR + Skill 包 ──[Run]──▶ 有结构的 AI 输出
                                      ↑
                                 [Guardrail 门禁]
                    ──[Bench]──▶ Vanilla vs RAG vs MindLakeVM 对比
```

---

## 三、设计模式分析

### 已有的好模式

| 模式 | 位置 | 说明 |
|------|------|------|
| 管道-过滤器 | `compiler/pipeline.py` | 7 阶段线性编译，职责清晰 |
| 仓储模式 | `store.py` / `tool_registry.py` | 统一 CRUD，隔离持久化 |
| 策略模式 | `tool_export.py` / `bench/baselines.py` | 按格式/基线分发执行逻辑 |
| Agent 循环 | `executor/agent_runner.py` | ReAct 模式，tool_use 多轮 |
| 守卫子句 | `executor/runner.py` + `guardrail.py` | 门禁短路，不进主流程 |
| 责任链 | `executor/verifier.py` | V1→V2→V3 串联验证 |

### 识别出的设计债务

1. **Repository 无接口抽象**：`store.py` 直接是函数模块，切换后端需要改所有调用处
2. **Strategy 无统一签名**：三个 baseline 函数签名不一致，需要 `if/elif` 分发
3. **Verifier 硬编码扩展点**：V1/V2/V3 写死在函数体内，无法动态注册
4. **双模式判断散落多处**：`tool_use vs json` 的环境变量判断分散在三个文件
5. **前端无状态管理**：各 Page 组件状态孤立，随功能增长会产生 prop drilling

---

## 四、本次实施的代码改进

### 改进 1：修复假 Trace

**文件**：`executor/tracer.py`、`executor/runner.py`

**问题**：`runner.py` 在 LLM 执行前就预生成了全部步骤标记为 `completed` 的 trace，是虚假数据。

**改动**：
- `make_trace()` 新增 `synthetic=True` 参数
- 单次执行模式下，每个步骤的 `notes` 标注 `[synthetic]`
- 新增 `make_pending_trace()`、`mark_step_running()`、`mark_step_completed()`、`mark_step_skipped()` 供 agent_runner 实时更新使用

### 改进 2：统一引用匹配逻辑

**文件**：`executor/verifier.py`、`bench/judges.py`、`bench/runner.py`

**问题**：verifier 用精确匹配，judges 用模糊匹配，bench runner 又是精确匹配，三套标准导致评测结果不可信。

**改动**：在 `verifier.py` 提取公共函数 `match_reference_path(expected, cited_paths)`，实现"精确匹配 → 关键词匹配"两级降级，三处统一调用。

### 改进 3：Judge 评测返回详情

**文件**：`bench/judges.py`、`bench/runner.py`

**问题**：`evaluate_case()` 只返回 `bool`，失败时不知道哪个 Judge 挂了。

**改动**：新增 `JudgeResult` 和 `CaseResult` 数据类，`evaluate_case()` 改返回 `CaseResult`，包含每个 Judge 的 `passed/fatal/reason` 明细。

### 改进 4：L1 编译时 IR 验证

**文件**：`compiler/ir_validator.py`（新建）、`compiler/pipeline.py`、`models.py`、`api/compile.py`

**改动**：
- 新增 Phase 5（L1 Gate），在编译完成后用 LLM 对照原文审查 IR：步骤遗漏、约束误判、知识覆盖率（0~1）
- 触发条件：请求传 `validate_ir: true` 或环境变量 `ENABLE_IR_VALIDATION=1`
- `CompileResponse` 新增 `ir_validation` 字段，包含 `coverage_score`、`missing_steps`、`constraint_issues`

---

## 五、当前系统能力边界

### 能做的

| 功能 | 入口 |
|------|------|
| 文档编译为 RNET IR + Skill 包 | `POST /compile` |
| 挂载 Skill 执行用户问题（含门禁） | `POST /run` |
| Three 组对比评测（Vanilla/RAG/MindLakeVM） | `POST /bench` |
| 管理已编译 Skill 列表和详情 | `GET /skills` / `GET /skills/{id}` |
| 导出为 Claude Tool / MCP Tool 格式 | `GET /skills/{id}/tool?format=claude` |
| 注册外部 CLI 工具并绑定到执行步骤 | `/tools` 系列端点 |
| 通过 MCP 协议接入 Claude Desktop | `/mcp` 端点 |

### 明确的边界

- 只支持粘贴文本或本地文件，不支持 URL/Notion/Confluence 等在线文档
- 每次执行只能挂载一个 Skill，不支持多 Skill 编排
- 重编译会覆盖旧版本，没有版本历史
- 全部存 JSON 文件，无并发保护，无多租户

---

## 六、在线文档接入设计（待实施）

在编译管线 Phase 0 之前插入 **Phase -1（Fetch）**，将任意在线文档拉取为纯文本后交给现有管道。

### 架构

```
URL / Notion / Confluence / 飞书
        │
        ▼
[Fetch Layer]  —— 策略模式 + 注册表
        │
        ▼ 纯文本（现有管道零改动）
[Ingest → Classify → ... → Package]
```

### 实现要点

```
compiler/fetchers/
    base.py              # DocumentFetcher ABC + FetchResult
    credential_store.py  # 从环境变量读取访问凭证
    web.py               # httpx + trafilatura
    pdf.py               # pdfminer.six
    notion.py            # Notion API
    confluence.py        # Confluence REST API
    feishu.py            # 飞书文档 API
    github.py            # GitHub raw 文件
```

**改动范围极小**：只扩展 `CompileRequest` 加 `document_url` 字段，修改 `resolve_document_content()` 加一个分支，现有所有测试不受影响。新增文档源只需实现 `can_handle()` + `fetch()` 并注册到 `_FETCHERS` 列表。

---

## 七、Skill 执行验证体系（已部分实施）

### 现有验证层（薄）

| 验证器 | 触发条件 | 本质 |
|--------|---------|------|
| V1 | format=json 且有 schema | JSON Schema 结构校验 |
| V2 | 有 required references | 引用路径字符串匹配 |
| V3 | 步骤数 > 10 | 计数阈值，非真正循环检测 |

均为**结构性验证**，无语义验证。

### 建议补充的验证层

```
L1  编译时验证  ← 本次已实施（ir_validator.py）
    IR 与原文一致性、覆盖率评分

L2  运行时验证  ← 现有 V1/V2/V3，待加 V4
    V4：LLM-as-Judge 对输出语义质量评分
    V5：硬约束未被输出层绕过

L3  回归测试    ← 待实施
    每个 Skill 绑定黄金测试用例
    重编译后自动对比指标变化
```

---

## 八、Skill Market 路线图

### 核心判断

现有 IR 标准化 + Bench 评测 + tool 导出三件事，恰好是 Skill Market 最难建立的**商品质量体系**。建议先做内部市场验证商业逻辑，再扩展到公开市场。

### 分阶段实施

**第一阶段（1~2周）：让 Skill 成为商品**

```python
class SkillManifest(BaseModel):
    publisher: str
    license: Literal["apache-2.0", "mit", "cc-by-4.0", "proprietary"]
    visibility: Literal["public", "org", "private"]
    tags: list[str]
    use_cases: list[str]
    risk_tier: Literal["low", "medium", "high"]
```

**第二阶段（1周）：版本管理**

存储结构从 `skills/{id}.json` 改为 `skills/{id}/versions/{kernel_id}.json`，保留全部历史版本，新增 `GET /skills/{id}/versions`。

**第三阶段（2周）：标准认证体系**

- 按 object_type 建立标准场景库（每类 2~3 个）
- `SkillCertification` 质量评级（A/B/C/F）
- 编译后自动跑标准场景，结果写入 Skill 元数据

**第四阶段（1~2周）：搜索与分发**

- 结构化过滤（domain/type/tag/grade）
- 语义搜索（`semantic_space` embedding，内存余弦相似度）
- `GET /skills/{id}/export?format=zip` 打包下载 + SHA256 校验

---

## 九、IR 质量优化方向

### 根本问题

当前编译是**单次 LLM 调用同时生成四核**，四核互相依赖但无法保证一致性。

### 六项优化方向（按优先级）

**优先级 1：约束原文锚定**（2~3天，收益最高）

每条 `hard_constraint` 必须附带原文引用：
```python
class ConstraintWithEvidence(BaseModel):
    constraint: str
    source_quote: str      # 原文原句
    source_location: str   # 位置描述
    severity: Literal["hard", "soft"]
```
这既提升门禁可信度，也是 Skill Market 质量背书的核心依据。

**优先级 2：分核编译**（3~5天）

将单次生成拆为四次独立 LLM 调用，前一核输出作为后一核输入：
```
[Phase R] → [Phase N] → [Phase E] → [Phase T]
```
E 核单独处理，约束识别精度大幅提升。

**优先级 3：T 核步骤粒度校准**（1~2天）

根据文档长度和类型自动计算步骤预算（3~12步），在 Phase T 的 prompt 中明确约束。

**优先级 4：LLM 替代关键字分类**（3~5天）

现有 `_classify()` 是纯词频统计，混合类型文档失效。改用小模型（gpt-4o-mini）做分类，返回 `(type, confidence)`，confidence < 0.7 时标记 mixed。

**优先级 5：Critic Pass 一致性自检**（1周）

四核生成后，用同一 LLM 自我审查跨核一致性（T.path 是否覆盖 N.constraints、E.hard_constraints 在 T.path 里是否有决策点处理等），发现问题后局部重生成。

**优先级 6：编译策略自动感知**（1天）

`strategy` 从用户手动选改为感知文档复杂度自动决策（文档 > 5000 字或约束密集 → detailed；< 800 字 → minimal）。

---

## 十、后续优先事项

```
近期（本月）
  1. 约束原文锚定（source_quote 字段）
  2. SkillManifest + 版本管理（为 Market 打基础）
  3. 用真实企业文档验证端到端质量

中期（下月）
  4. 分核编译（先拆 E 核）
  5. 标准 Bench 场景库 + 质量认证
  6. 在线文档接入（Fetcher 层）

远期
  7. 搜索 + 打包分发
  8. V4 语义验证（LLM-as-Judge）
  9. 黄金测试集 + Regression 自动化
  10. 多 Skill 编排
```

---

*文档由开发会话自动整理，反映截至 2026-03-28 的系统状态与设计决策。*

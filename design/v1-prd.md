下面是一份可直接落地执行的**产品设计文档（PRD）**，面向你要演示/商业化的 **MindLakeOS Demo：Semantic Kernel Compiler + Runtime**。文档按“产品—工程—指标—交付”顺序组织，并把核心能力严格映射到 **R/N/E/T 四核**，方便你路演、招人、对齐开发。

---

# MindLakeOS Demo 产品设计文档（PRD）

**产品名**：MindLakeOS Demo（Doc2Skill 认知编译平台）
**版本**：v0.1（Demo 可交付）
**目标**：把企业“固态文档”一键编译成可挂载、可验证、可执行的“液态 Skill”，并在运行时提供可追溯的执行轨迹与治理门禁。

---

## 1. 背景与问题定义

### 1.1 行业现状

企业知识大量存在于 SOP / Policy / RFC / Wiki / PDF 中：

* 可读但不可执行（人能看懂，AI 不能稳定执行）
* “RAG 能找，但不一定会用”，且对**流程、红线、异常分支**支持弱
* 传统 Prompt/Workflow 难以版本化、难以验证、难以复用

### 1.2 核心痛点（Demo 必须打中）

1. **执行不稳定**：同一问题改写一下输出漂移（高不确定性）
2. **合规不可控**：红线/审批条件容易遗漏
3. **上下文浪费**：大量 token 用在复述文档或无关内容
4. **不可资产化**：提示词/经验无法形成可复用的“组织资产”

### 1.3 机会点（你的独特性）

用 **R/N/E/T 四核**做“认知指令集 + 编译器 + 运行时门禁”，把文本知识变成**可执行协议资产**：

* **R**：语义坐标锚定（domain/object/semantic space）
* **N**：可登记/可索引/可拆分的知识资产组织（progressive disclosure）
* **E**：熵控与治理门禁（hard/soft constraints + validation）
* **T**：可追溯的执行路径（steps/decision points/tool routing）

---

## 2. 产品目标与非目标

### 2.1 产品目标（v0.1 Demo）

* **G1：一键编译**：输入一份文档，生成 RNET IR + Skill 目录
* **G2：可执行**：挂载 Skill 后回答问题，按 T 路径执行
* **G3：可验证**：输出必须通过 E 核校验（schema/引用/停止规则）
* **G4：可展示**：UI 上可视化四核、目录树、执行 trace、拦截原因
* **G5：可对比**：提供 bench，对比 vanilla / rag / mindlake 的关键指标

### 2.2 非目标（v0.1 不做）

* 不做“通用企业知识库平台”
* 不做复杂多租户权限体系（只做 Demo 级门禁占位）
* 不做全量自动化工具生态（只做少量内置 tool stub）

---

## 3. 用户与使用场景

### 3.1 目标用户（Demo 观众画像）

* 企业 CTO/技术负责人：关心“可靠执行 + 合规”
* 产品/运营负责人：关心“沉淀资产 + 规模化复制”
* 评委/投资人：关心“壁垒 + 指标提升 + 演示冲击力”

### 3.2 核心使用场景（必须支持）

**S1：SOP 执行与拦截**

* 文档含“禁止高峰期扩容”“必须 CTO 授权”等红线
* 问题包含触发条件 → 系统应拦截并要求补充授权/证据

**S2：流程型政策问答（带表格/例外条款）**

* 文档有审批矩阵、报销规则、例外分支
* 系统必须引用 references 中对应条款/表格行

**S3：技术 RFC 解析（结构化输出）**

* 文档要求输出 JSON 方案/字段
* 系统输出必须通过 schema 校验

---

## 4. 产品形态与信息架构

### 4.1 产品形态

* **Web UI（3 页）** + **Runtime API（compile/run/skills/bench）**
* 后端核心：Compiler（v0.3）+ Renderer（v0.4）+ Verifier + Executor

### 4.2 关键概念（面向 UI 展示）

* **IR（SemanticKernelIR）**：四核 JSON（R/N/E/T）
* **Skill 包**：`SKILL.md` + `references/` + `assets/` + `scripts/`
* **Trace**：运行时每一步执行记录（对应 T.path）
* **Violations**：触发的 E 核硬约束与拦截理由
* **Evidence**：引用到的 references 文件/片段

---

## 5. 核心功能需求（按页面/模块）

### 5.1 Compile 页（固态 → IR → Skill）

**用户故事**

* 作为演示者，我上传 SOP 文档并点击 Compile，系统生成 IR 和 Skill 目录，并在 UI 上展示四核面板与目录树。

**功能点**

1. 文档输入：选择 examples 或粘贴文本
2. 策略选择：Minimal/Default/Detailed（CompilationStrategy）
3. 编译：显示

   * Cache hit/相似度/Kernel ID
   * IR（四核面板）
4. 渐进披露结果：目录树 + 打开文件预览
5. 可选：MetaIgnoranceProbe 结果（blind spots）

**四核字段映射（UI 必须展示）**

* R：domain / object_type / semantic_space
* N：structure / schema / constraints + references 链接
* E：format / target_entropy / hard_constraints / soft_constraints / meta_ignorance
* T：path / cot_steps

---

### 5.2 Run 页（挂载 Skill → 执行 → trace + 证据 + 门禁）

**用户故事**

* 作为演示者，我选择一个 Skill，输入“会触发红线”的问题，系统必须拦截，并展示触发的硬约束与引用证据。
* 作为演示者，我输入合规问题，系统按步骤执行并引用 references，输出结构化结果。

**功能点**

1. Skill Selector：列出已生成 skill
2. 运行：输入问题 → `/run`
3. 输出区：最终回答（或拦截提示）
4. 右侧执行检查器：

   * TraceTimeline：T.path 每步状态
   * EvidenceViewer：引用文件/片段
   * Guardrail Panel：校验结果 + violations

**必须支持的验证器（v0.1 最小集）**

* V1：Schema 校验（若 E/N 给出 schema）
* V2：引用校验（要求引用 references 的至少 1 条证据，可配置）
* V3：停止规则（检测循环/重复，或超过步数停止）

---

### 5.3 Bench 页（对比指标，证明“降熵收益”）

**用户故事**

* 作为演示者，我选择一个场景，一键跑 vanilla/rag/mindlake，对比 token 成本、成功率、引用率、拦截正确率。

**指标（最少 4 个）**

* Token cost（in/out/total）
* Success rate（是否满足任务）
* Citation/Evidence rate（是否给出证据引用）
* Guardrail block rate（拦截次数、误拦/漏拦）

**结果展示**

* 对比表（每组一行）+ 右侧摘要卡（节省%、下降%）

---

## 6. 关键体验与交互规格（最小线框文字版）

### 6.1 全局布局

* 左侧导航：Compile / Run / Bench
* 顶部：当前 skill / 当前场景 / 模型信息（可隐藏）
* 统一组件：**RNETPanel**（每页必须可打开）

### 6.2 RNETPanel（统一组件）

* Tabs：R / N / E / T（默认显示摘要 + 可展开）
* 每个 Tab：字段 + “解释一句话”（面向观众）
* 在 Run 页叠加：显示每个 T step 的状态徽章、E violations 红色标记

---

## 7. 数据与接口设计

### 7.1 核心数据结构（概念）

* `SemanticKernelIR`
* `SkillPackage`（目录树 + manifest + 文件列表）
* `RunResult`（output + trace + evidence + validation）
* `BenchResult`（metrics 表 + summary）

### 7.2 API（最小集合）

* `POST /compile`

  * in：task_description, strategy, force_recompile, enable_probe
  * out：ir, cache_hit, similarity, kernel_id, artifacts(files_tree)
* `GET /skills`
* `GET /skills/{id}`
* `POST /run`

  * in：skill_id, user_input
  * out：output_text, blocked, violations[], trace, evidence[], validation
* `POST /bench`

  * in：scenario_id, baselines[]
  * out：results_table[], report_summary

---

## 8. 质量、安全、合规（E 核落地）

### 8.1 质量门禁（E 核最小闭环）

* 输出格式：强制 JSON 或 structured（由 E.format 控制）
* 硬约束：触发即拦截（blocked=true）
* 软约束：不满足则降级提示/重试（可选）

### 8.2 风险控制（Demo 级）

* 防止“编译器输出非法 JSON”：tolerant parse + schema 校验
* 防止“胡编证据”：证据必须来自 references 文件路径
* 防止“无限输出”：最大步数/最大 tokens/循环检测

---

## 9. Bench 评测方案（把“玄学”变成数字）

### 9.1 三组对比定义

* Vanilla：直接问模型（baseline prompt）
* RAG：检索拼接后问模型（简化实现即可）
* MindLakeOS：compile → mount skill → run with verifier/executor

### 9.2 成功判定（每场景定义）

* SOP 场景：是否正确拦截 + 是否要求授权/条件
* 政策场景：是否引用正确条款 + 结果是否正确
* RFC 场景：是否输出符合 schema 的 JSON

---

## 10. 交付计划（Demo 导向）

### 10.1 v0.1 必交付清单

* [ ] 3 份 examples（SOP/政策/RFC）
* [ ] compile/run/skills/bench API 跑通
* [ ] UI 3 页 + RNETPanel + 目录树 + trace
* [ ] verifier：schema + 引用 + 停止规则（最小闭环）
* [ ] bench：至少一个场景一键对比出表

### 10.2 Demo 彩排脚本（必备）

* 固态文档 → 编译 → skill 目录树
* 挂载 → 提问触发红线 → 拦截 + 引用证据
* bench → 指标对比卡（节省 token、降低失败率）

---

## 11. 关键风险与应对

1. **LLM 编译不稳定**：

   * 方案：Detailed 策略兜底 + tolerant parse + 必填字段校验
2. **证据引用不足**：

   * 方案：E 核加“必须引用 references 至少 N 条”的硬约束
3. **演示不够震撼**：

   * 方案：SOP 场景必须包含“会导致事故”的红线，形成强对比
4. **指标跑不出差异**：

   * 方案：bench 场景要设计成“RAG 也会漏红线/漏例外”的类型

---

## 12. 四核总结（给评委的一页纸）

* **R（表示）**：把任务从“自然语言”变成“可定位的语义坐标”
* **N（注册）**：把长文档拆成可检索可复用的资产目录（渐进披露）
* **E（熵控）**：用可执行门禁把不确定性收敛成工程可控
* **T（转换）**：把执行过程显式化成可追溯路径与决策点

---



1. **接口与 DTO 规范（OpenAPI/JSON Schema）**
2. **Bench 场景 YAML 模板 + 评测规则（success 判定细则）**


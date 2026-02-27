# Demo 仓库结构 v0.1

本文档定义 MindLakeOS Demo 的完整仓库目录结构，供开发团队参考对齐。

---

## 顶层结构

```text
mindlakeVM/
├── specs/                          # 规范库（本目录）
├── design/                         # 产品设计文档
├── docs/                           # 理论文档
├── cps-research/                   # 编译管线研究
├── mindlakevm/                     # 核心实现（待填充）
│   ├── runtime/                    # 后端运行时
│   ├── ui/                         # 前端 Web UI
│   ├── examples/                   # 示例文档与 Skill 包
│   └── bench/                      # 评测框架
└── README.md
```

---

## `mindlakevm/runtime/` — 后端运行时

```text
mindlakevm/runtime/
├── main.py                         # 入口，启动 FastAPI/Flask 服务
├── api/
│   ├── compile.py                  # POST /compile 路由
│   ├── skills.py                   # GET /skills, GET /skills/{id} 路由
│   ├── run.py                      # POST /run 路由
│   └── bench.py                    # POST /bench 路由
├── compiler/
│   ├── pipeline.py                 # 7 阶段编译管线入口
│   ├── ingest.py                   # Phase 0: 文档摄入与归一化
│   ├── classify.py                 # Phase 1: 文档类型识别
│   ├── extract.py                  # Phase 2: 认知结构抽取 → CP Spec
│   ├── synthesize.py               # Phase 3: 渐进披露分层
│   ├── package.py                  # Phase 4: Skill 包生成
│   ├── validate.py                 # Phase 5: 静态校验
│   └── ir_schema.py                # IR 结构定义（对齐 ir_schema_v0.3.json）
├── executor/
│   ├── runner.py                   # Skill 执行器（挂载 + 运行）
│   ├── verifier.py                 # 验证器（V1/V2/V3）
│   ├── guardrail.py                # E 核硬约束检查
│   └── tracer.py                   # T 核执行 trace 记录
├── bench/
│   ├── runner.py                   # Bench 评测入口
│   ├── baselines/
│   │   ├── vanilla.py              # Vanilla baseline
│   │   ├── rag.py                  # RAG baseline
│   │   └── mindlakevm.py           # MindLakeOS baseline（调用 /run）
│   ├── judges/
│   │   ├── guardrail_block.py      # Judge: 门禁拦截
│   │   ├── no_false_positive.py    # Judge: 无误拦截
│   │   ├── evidence_cited.py       # Judge: 引用充分
│   │   ├── output_schema_valid.py  # Judge: schema 校验
│   │   ├── trace_coverage.py       # Judge: trace 覆盖
│   │   └── output_keywords.py      # Judge: 关键词匹配
│   └── scenario_loader.py          # 加载 specs/bench/scenarios/*.yaml
├── skills/                         # 已编译 Skill 存储目录
│   └── {skill_id}/
│       ├── SKILL.md
│       ├── references/
│       ├── assets/
│       └── scripts/
└── requirements.txt
```

---

## `mindlakevm/ui/` — 前端 Web UI

```text
mindlakevm/ui/
├── src/
│   ├── pages/
│   │   ├── CompilePage.tsx         # Compile 页（固态 → IR → Skill）
│   │   ├── RunPage.tsx             # Run 页（挂载 → 执行 → trace）
│   │   └── BenchPage.tsx           # Bench 页（对比指标）
│   ├── components/
│   │   ├── RNETPanel/
│   │   │   ├── RNETPanel.tsx       # 四核面板（全局统一组件）
│   │   │   ├── RTab.tsx            # R 核 Tab
│   │   │   ├── NTab.tsx            # N 核 Tab
│   │   │   ├── ETab.tsx            # E 核 Tab（硬约束红标）
│   │   │   └── TTab.tsx            # T 核 Tab（路径图）
│   │   ├── compile/
│   │   │   ├── DocumentInput.tsx   # 文档输入（粘贴/选择 example）
│   │   │   ├── StrategySelector.tsx # 策略选择（minimal/default/detailed）
│   │   │   ├── FilesTree.tsx       # 目录树展示
│   │   │   └── CompileStatus.tsx   # 编译状态（cache_hit/similarity）
│   │   ├── run/
│   │   │   ├── SkillSelector.tsx   # Skill 选择器
│   │   │   ├── TraceTimeline.tsx   # T 核执行时间线
│   │   │   ├── EvidenceViewer.tsx  # N 核引用证据查看器
│   │   │   └── GuardrailPanel.tsx  # E 核门禁面板（violations 红标）
│   │   └── bench/
│   │       ├── CompareTable.tsx    # 对比表（三组指标）
│   │       └── SummaryCard.tsx     # 摘要卡（节省%/提升%）
│   ├── api/
│   │   └── client.ts               # API 客户端（对齐 openapi_v0.1.yaml）
│   └── App.tsx
├── public/
└── package.json
```

---

## `mindlakevm/examples/` — 示例文档与 Skill 包

```text
mindlakevm/examples/
├── docs/
│   ├── sop_incident_response.md   # SOP 示例：SEV1 故障应急响应
│   ├── policy_reimbursement.md    # 政策示例：员工报销政策
│   └── rfc_api_gateway.md         # RFC 示例：API 网关设计规范
└── skills/                         # 预编译的 Skill 包（路演用）
    ├── ops-sev1-incident-response/
    │   ├── SKILL.md
    │   ├── references/
    │   │   ├── ESCALATION_MATRIX.md
    │   │   └── SEVERITY_THRESHOLDS.md
    │   └── assets/
    │       └── incident_report_template.md
    ├── finance-reimbursement-policy/
    │   ├── SKILL.md
    │   ├── references/
    │   │   ├── APPROVAL_MATRIX.md
    │   │   ├── CATEGORY_LIMITS.md
    │   │   ├── EXCEPTION_RULES.md
    │   │   └── REJECTION_RULES.md
    │   └── assets/
    │       └── reimbursement_form_template.md
    └── engineering-api-design-rfc/
        ├── SKILL.md
        ├── references/
        │   ├── FIELD_DEFINITIONS.md
        │   └── SECURITY_RULES.md
        └── assets/
            └── gateway_config_schema.json
```

---

## 关键文件职责说明

### `SKILL.md` 格式规范

每个 Skill 包的 `SKILL.md` 必须包含：

```markdown
---
name: {skill-id}               # kebab-case，与目录同名
description: |
  {一句话功能描述}。触发关键词：{kw1}、{kw2}、{kw3}
metadata:
  org.owner: "{team}"
  org.risk_tier: "{low|medium|high}"
  org.semver: "1.0.0"
  org.approval_status: "approved"
---

## 角色与目标
...

## 核心流程
...

## 关键决策点
...

## 输出格式
...

## 验证清单（自检）
- [ ] ...

## 边界与例外
...

## 参考资料
- [ESCALATION_MATRIX](references/ESCALATION_MATRIX.md)
```

---

## 开发启动顺序建议

1. 先确认 `specs/api/openapi_v0.1.yaml` 字段定义
2. 实现 `runtime/compiler/` 核心管线
3. 用 `examples/docs/` 中的三份文档跑通 `/compile`
4. 实现 `runtime/executor/` + verifier
5. 跑通 `/run`（含 guardrail 拦截）
6. 实现 `runtime/bench/` 跑通 `/bench`
7. 开发 UI 三页，以 `specs/api/examples/` 为 mock
8. 联调 + 路演彩排

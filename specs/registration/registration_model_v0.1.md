# MindLakeVM Registration Model v0.1

本文档定义 MindLakeVM 的统一注册模型。  
目标不是说明“有哪些配置表”，而是规定：

- 哪些对象被系统承认为第一类对象
- 对象如何获得稳定身份
- 对象如何进入系统秩序
- 对象、关系、实例与治理记录如何分层注册

一句话：

> 注册，不是把对象记下来，而是把对象纳入系统秩序。

---

## 1. 设计目标

MindLakeVM 的注册体系需要同时满足以下目标：

1. 对象身份稳定
2. 对象类型显式
3. 对象关系可追踪
4. 对象实例可治理
5. 对象状态可恢复
6. 对象结果可审计

注册体系服务的不是单一目录，而是完整闭环：

```text
对象定义
  → 对象注册
  → 关系绑定
  → 运行实例化
  → 治理与验证
  → 恢复与审计
```

---

## 2. 核心判断

### 2.1 注册是“系统存在”而不是“语义存在”

一个对象即使在文档里被提到、在提示词里被描述、在代码中被临时拼出来，也不代表它已成为系统对象。

只有当它具备以下属性时，才算被正式注册：

- 有 `id`
- 有 `kind`
- 有版本或演化边界
- 有 owner / source / scope
- 可被枚举
- 可被引用
- 可被验证

### 2.2 注册不是平面目录，而是分层对象体系

MindLakeVM 的注册应至少覆盖四层：

1. 定义对象注册
2. 关系对象注册
3. 运行对象注册
4. 治理对象注册

### 2.3 注册是 Runtime / Kernel 的前提

未注册对象不得直接进入：

- `/run`
- trace
- verifier
- tool adapter
- policy gate
- checkpoint

换句话说：

> 没有注册，就没有稳定运行时。

---

## 3. 注册对象分层

## 3.1 定义对象注册

定义对象回答“它是什么”。

### 3.1.1 Skill

表示已编译的知识协议对象。

最小字段：

```yaml
kind: Skill
skill_id: llmos-kernel-architecture
kernel_id: llmos-kernel-architecture-v1
domain: llmos.kernel
object_type: spec
compiled_at: "2026-03-25T10:00:00Z"
source_doc: docs/llmos_kernel_architecture_case.md
```

### 3.1.2 ToolHandle

表示受治理的外部能力句柄对象。

最小字段：

```yaml
kind: ToolHandle
tool_id: cli_anything_libreoffice
provider: cli-anything
command: cli-anything-libreoffice
capabilities:
  - document.read
  - document.edit
side_effect_level: write_optional
status: active
```

定义对象注册要求：

- `id` 唯一
- `kind` 明确
- 配置可序列化
- 可被 list / get

---

## 3.2 关系对象注册

关系对象回答“对象如何连接”。

### 3.2.1 ToolBinding

把 Skill 的某个 step 绑定到 ToolHandle。

最小字段：

```yaml
kind: ToolBinding
binding_id: bind_office_edit_step_1
skill_id: office-doc-edit
step_id: edit-document
tool_id: cli_anything_libreoffice
arg_mapping:
  input_path: $input.document_path
  output_path: $runtime.temp_output_path
enabled: true
```

关系对象注册要求：

- 必须引用已注册对象
- 必须校验引用存在性
- 必须具备启停能力
- 不得依赖匿名字符串关系

---

## 3.3 运行对象注册

运行对象回答“它现在如何活着”。

### 3.3.1 ToolInvocation

表示一次具体工具调用。

```yaml
kind: ToolInvocation
invocation_id: invoke_001
tool_id: cli_anything_libreoffice
process_id: proc_001
step_id: edit-document
timeout_ms: 30000
dry_run: false
```

### 3.3.2 Process

表示统一预算 owner 和执行生命周期的活体对象。

```yaml
kind: Process
process_id: proc_001
skill_id: office-doc-edit
state: running
owner: run_request_001
```

### 3.3.3 Frame

表示局部执行位面。

```yaml
kind: Frame
frame_id: frame_001
process_id: proc_001
step_id: edit-document
status: running
```

运行对象注册要求：

- 必须具备 owner / parent 归属
- 必须具备生命周期状态
- 必须允许 trace / recovery 引用

---

## 3.4 治理对象注册

治理对象回答“系统如何管它”。

### 3.4.1 Event

```yaml
kind: Event
event_id: evt_001
event_type: tool_call_requested
source: frame_001
target: cli_anything_libreoffice
process_id: proc_001
```

### 3.4.2 Budget

```yaml
kind: BudgetState
budget_id: budget_001
owner_ref: proc_001
token:
  allocated: 12000
  used: 3200
```

### 3.4.3 PolicyDecision

```yaml
kind: PolicyDecision
decision_id: pol_001
tool_id: cli_anything_libreoffice
allowed: false
reason: requires confirmation
```

### 3.4.4 Checkpoint

```yaml
kind: Checkpoint
checkpoint_id: ckpt_001
process_id: proc_001
frame_ref: frame_001
```

治理对象注册要求：

- 必须能归因到 process / frame / invocation
- 必须可回放或可审计
- 必须具备时间戳或序号边界

---

## 4. 统一注册原则

### 4.1 唯一身份原则

所有注册对象必须具备全局唯一或域内唯一 ID。

### 4.2 类型显式原则

所有注册对象必须显式声明 `kind`。

### 4.3 引用闭包原则

关系对象与运行对象引用的目标，必须先已注册。

### 4.4 治理前置原则

高风险动作相关对象必须在执行前已完成注册和可解析。

### 4.5 审计可归因原则

所有运行与治理对象必须能追溯到：

- 所属 process
- 所属 skill / step
- 触发来源

### 4.6 恢复可定位原则

所有可恢复执行必须能定位到：

- Process
- Frame
- Checkpoint
- 最近相关 Event

---

## 5. 注册表分工

MindLakeVM 当前与目标中的注册表可拆成以下角色：

### 5.1 Skill Registry

负责：

- 已编译 skill 的索引
- `skill_id -> IR / package`
- bundle 文件定位

### 5.2 Tool Registry

负责：

- `ToolHandle` 存储
- CLI-Anything registry 导入
- probe / list / get

### 5.3 Binding Registry

负责：

- `ToolBinding`
- `skill + step -> tool`

### 5.4 Runtime Registry（目标态）

负责：

- Process
- Frame
- Invocation
- Event cursor
- Checkpoint pointer

### 5.5 Governance Registry（目标态）

负责：

- BudgetState
- PolicyDecision
- RecoveryRecord
- Audit trail

---

## 6. 当前落地映射

当前代码中的注册分布如下：

| 对象层 | 当前文件 | 当前状态 |
|--------|---------|---------|
| Skill | `store.py` | 已实现 |
| ToolHandle | `tool_registry.py` | 已实现 |
| ToolBinding | `tool_registry.py` | 已实现 |
| ToolInvocation | `runner.py` 运行时构造 | 初步实现 |
| ToolExecutionResult | `tool_adapter.py` | 已实现 |
| Process / Frame | `runner.py` + `tracer.py` | 半结构化 |
| Event | trace / result 中隐含 | 未正式注册 |
| BudgetState | `usage` 与运行逻辑中部分体现 | 未正式注册 |
| PolicyDecision | `runner.py` | 初步实现 |

---

## 7. 推荐演进路线

### Phase 1：统一定义对象注册

- 固化 `Skill`
- 固化 `ToolHandle`
- 固化 `ToolBinding`

### Phase 2：统一运行对象注册

- 引入 `Process`
- 引入 `Frame`
- 引入 `ToolInvocation` registry

### Phase 3：统一治理对象注册

- 引入 `EventEnvelope`
- 引入 `BudgetState`
- 引入 `Checkpoint`
- 引入 `PolicyDecision` store

### Phase 4：形成统一注册 API

建议最终具备：

- `GET /registry/skills`
- `GET /registry/tools`
- `GET /registry/bindings`
- `GET /registry/processes`
- `GET /registry/events`
- `GET /registry/budgets`

---

## 8. 最小不变量

以下不变量必须成立：

1. 未注册 Tool 不得被 `/run` 直接调用
2. 未注册 Binding 不得驱动 step 进入外部执行
3. 所有 ToolExecutionResult 必须能追溯到 ToolInvocation
4. 所有 PolicyDecision 必须能追溯到 step / tool / process
5. 所有 Budget 变更必须可归因到 process 或 invocation
6. 所有可恢复对象必须至少关联一个 checkpoint 边界

---

## 9. 总结

MindLakeVM 的注册思想，不是某个孤立模块，而是一条逐渐展开的系统主线：

- Skill 注册：让知识成为协议对象
- Tool 注册：让外部能力成为执行句柄
- Process 注册：让请求成为活体
- Event 注册：让变化成为控制对象
- Budget 注册：让资源成为治理原语

最终目标不是拥有很多 registry，而是形成：

> 一个统一的、分层的、可治理的注册体系。

在这个体系中，注册的真正含义是：

> 把对象从语义存在提升为系统存在。

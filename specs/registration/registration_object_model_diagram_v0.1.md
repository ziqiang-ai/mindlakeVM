# Registration Object Model Diagram v0.1

本文档给出 `models.py + registry.py` 对应的统一注册对象模型设计图。  
目标：说明当前实现与目标态之间的对象分层、注册表分工与运行时流向。

---

## 1. 对象分层图

```mermaid
graph TD
    subgraph Definition["定义对象层"]
        Skill["Skill"]
        ToolHandle["ToolHandle"]
    end

    subgraph Relation["关系对象层"]
        ToolBinding["ToolBinding"]
    end

    subgraph Runtime["运行对象层"]
        Process["Process"]
        Frame["Frame"]
        ToolInvocation["ToolInvocation"]
        ToolExecutionResult["ToolExecutionResult"]
    end

    subgraph Governance["治理对象层"]
        Event["EventEnvelope"]
        Budget["BudgetState"]
        PolicyDecision["PolicyDecision"]
        Checkpoint["Checkpoint"]
    end

    Skill --> ToolBinding
    ToolHandle --> ToolBinding
    ToolBinding --> Frame
    Process --> Frame
    Frame --> ToolInvocation
    ToolInvocation --> ToolExecutionResult
    ToolExecutionResult --> Event
    Process --> Budget
    ToolInvocation --> PolicyDecision
    Process --> Checkpoint
    Event --> Checkpoint
```

---

## 2. 当前代码映射图

```mermaid
graph LR
    Models["models.py"] --> SkillModels["Skill / IR / RunResponse"]
    Models --> ToolModels["ToolHandle / ToolBinding / ToolExecutionResult"]

    Store["store.py"] --> SkillRegistry["Skill Registry"]
    ToolRegistry["tool_registry.py"] --> ToolHandleRegistry["ToolHandle Registry"]
    ToolRegistry --> BindingRegistry["ToolBinding Registry"]

    Runner["executor/runner.py"] --> Invocation["ToolInvocation"]
    Runner --> Policy["ToolPolicyDecision"]
    Runner --> Trace["TraceStep / Evidence"]

    ToolAdapter["executor/tool_adapter.py"] --> ExecResult["ToolExecutionResult"]
    ApiTools["api/tools.py"] --> ToolHandleRegistry
    ApiTools --> BindingRegistry
```

---

## 3. 注册流向图

```mermaid
sequenceDiagram
    participant Doc as Document
    participant Compile as /compile
    participant SkillReg as Skill Registry
    participant ToolReg as Tool Registry
    participant BindReg as Binding Registry
    participant Run as /run
    participant CLI as CLI Tool

    Doc->>Compile: compile document
    Compile->>SkillReg: register Skill + IR + bundle
    ToolReg->>ToolReg: register ToolHandle
    BindReg->>BindReg: register ToolBinding
    Run->>SkillReg: resolve skill + step
    Run->>BindReg: resolve binding
    Run->>ToolReg: resolve tool handle
    Run->>CLI: invoke command
    CLI-->>Run: JSON result
    Run->>Run: emit trace / evidence / policy decision
```

---

## 4. 目标态统一注册表

```mermaid
graph TD
    Root["Unified Registration Layer"]

    Root --> SkillReg["Skill Registry"]
    Root --> ToolReg["Tool Registry"]
    Root --> BindingReg["Binding Registry"]
    Root --> ProcessReg["Process Registry"]
    Root --> EventReg["Event Registry"]
    Root --> BudgetReg["Budget Registry"]
    Root --> RecoveryReg["Checkpoint / Recovery Registry"]

    SkillReg --> Skill["Skill / IR / Bundle"]
    ToolReg --> Tool["ToolHandle"]
    BindingReg --> Binding["ToolBinding"]
    ProcessReg --> Process["Process / Frame / Invocation"]
    EventReg --> Event["EventEnvelope"]
    BudgetReg --> Budget["BudgetState"]
    RecoveryReg --> Recovery["Checkpoint / RecoveryRecord"]
```

---

## 5. 设计说明

### 当前已具备

- Skill 注册
- ToolHandle 注册
- ToolBinding 注册
- ToolExecutionResult 结构化
- PolicyDecision 初步结构化

### 当前未完成

- Process Registry
- Event Registry
- Budget Registry
- Checkpoint Registry
- 统一的 registry API 聚合层

### 核心设计原则

1. 定义对象与运行对象分离
2. 注册表按层分工，不做平面大表
3. 关系对象必须显式注册
4. 治理对象最终必须具备独立注册能力

---

## 6. 一句话总结

这张图表达的核心不是“有哪些类”，而是：

> Skill、Tool、Binding、Process、Event、Budget、Checkpoint 如何通过注册体系被纳入同一个运行时秩序。

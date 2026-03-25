---
name: llmos-kernel-architecture
description: |
  用于解释和执行 LLMOS Kernel 相关架构判断。触发关键词：Cognitive ABI、Agent Process、Kernel Step Loop、Event Flow、Policy Hook。
metadata:
  org.owner: "llmos"
  org.risk_tier: "high"
  org.semver: "0.1.0"
  org.approval_status: "draft"
---

## 角色与目标

你是一个面向 LLMOS / Agent Runtime 设计者的架构解释与执行 Skill。

目标：
- 解释 LLMOS Kernel 的核心对象和控制关系
- 回答 Cognitive ABI、Agent Process、Kernel Step Loop 之间的关系
- 给出实现层面的约束、边界和后续工程方向
- 在回答时尽量结构化，避免泛泛而谈

适用场景：
- 讨论 Agent Kernel 架构
- 讨论 Runtime 与 Skill 的接缝
- 讨论 Event、Budget、Policy、Checkpoint 的角色
- 讨论规范如何落到工程实现

不适用场景：
- 纯业务功能问答
- 与 LLMOS Kernel 无关的普通编程问题
- 无需架构约束的闲聊式讨论

## 核心概念

### ABI
ABI 是应用二进制接口。
它解决的不是源码层怎么调用，而是编译后对象如何在机器层兼容协作。

### Cognitive ABI
Cognitive ABI 是 Skill / IR / Runtime / Kernel 之间的最低执行接入契约。
它规定：
- 对象身份
- step 输入输出封装
- 错误模型
- 预算变化
- 挂起与恢复
- 提交与回滚边界

### Event Flow
事件流是系统内部有意义变化的统一载体。
它不是日志，而是状态转移在时间中的展开形式。

### Object Model
对象模型规定系统里有哪些第一类对象，以及这些对象的字段、关系、生命周期和行为。

### Policy Hook
Policy Hook 是 Kernel 在关键执行边界上插入策略判断的挂钩点。
它决定某个动作是否允许、是否需要确认、是否应该 defer。

## 核心对象

### Skill
能力定义对象。
回答：这个能力是什么。

### IR
认知程序中间表示对象。
回答：这个能力如何被执行。

### Frame
运行时局部执行实例对象。
回答：当前局部执行到了哪里。

### Event
状态转移与控制传播对象。
回答：刚刚发生了什么，以及接下来谁应该响应。

### Budget
资源与熵治理对象。
回答：还能不能继续执行，以及代价如何被约束。

### Tool
外部能力句柄对象。
回答：系统如何以受控方式连接外部世界。

### Agent Process
最小可治理的持续执行单元。
回答：谁是被 Kernel 整体接管的活体。

## 三份核心规范

### 1. Cognitive ABI Spec

目标：
规定 Skill IR、Process、Frame、Tool、Budget、Event 如何进入 Runtime / Kernel 的最低执行边界。

覆盖对象：
- IRHandle
- ProcessHandle
- FrameHandle
- ToolHandle
- BudgetHandle
- EventEnvelope

关键要求：
- step 输入显式化
- step 输出结构化
- 错误结构化
- 预算变化可归因
- 所有外部能力调用必须经过 ToolHandle
- 所有副作用必须经过显式 commit boundary

核心判断：
对象模型定义了零件宇宙，Cognitive ABI 定义了零件装配与运动的接口。

### 2. Agent Process Spec

目标：
定义 LLMOS 中最小可治理的持续执行单元。

关键判断：
- Skill 不是活体
- IR 不是活体
- Frame 是局部执行位面
- Process 才是被 Kernel 整体接管的生命体

Process 至少承载：
- 根目标
- 根 IR
- 一组 Frame
- 一组 Budget
- 一组 Capability / Tool Handle
- 生命周期
- Checkpoint / Recovery 边界

最小生命周期：
- created
- ready
- running
- yielded
- blocked
- resumed
- committing
- committed
- failed
- rolled_back
- terminated

### 3. Kernel Step Loop Spec

目标：
定义 Kernel 一次最小推进循环应该做什么。

标准时序：
1. load
2. inspect
3. authorize
4. reserve
5. execute
6. emit
7. apply
8. checkpoint
9. decide
10. commit / rollback / yield / block / terminate

关键解释：
- inspect：当前状态是否合法
- authorize：当前动作是否被 policy 允许
- reserve：预算是否足够且已预留
- execute：执行当前 IR node
- emit：把结果转成 event
- apply：把状态补丁写回系统内部对象
- checkpoint：在安全边界保存可恢复状态
- decide：本次 step 落到哪个稳定边界

核心判断：
Kernel Step 不是完成整个任务，而是把 Process 推进到下一个稳定边界。

## 控制链

系统最小控制链：

Skill / IR
-> Cognitive ABI bind
-> Agent Process / Frame
-> Kernel Step Loop
-> Event / Budget / Policy / Checkpoint
-> Commit / Rollback / Yield / Block / Terminate

Kernel 的一句话定义：

Kernel = 以 Event 驱动 Frame 的状态转移，并在关键边界上施加 Budget / Policy 约束。

## Policy Hook 规则

Policy Hook 至少应该支持以下挂钩点：
- pre_step
- pre_tool_call
- pre_commit
- post_event

Policy decision 至少应支持：
- allow
- deny
- defer
- confirm

Policy Hook 与 Budget Hook 区分：
- Policy Hook 问：该不该做
- Budget Hook 问：做不做得起

## 验证清单（自检）

- [ ] 是否明确区分了 Skill、IR、Frame、Process
- [ ] 是否明确说明了 Event 不是日志而是控制对象
- [ ] 是否明确说明了 Budget 是治理对象
- [ ] 是否明确说明了 Tool 是句柄对象而不是裸函数
- [ ] 是否明确给出了 Step Loop 的 10 个阶段
- [ ] 是否明确给出了 Policy Hook 的位置与职责
- [ ] 是否明确说明了 Checkpoint / Commit / Rollback 的边界

## 边界与例外

### 硬约束
- 不得把 SkillSpec 直接当作运行时实例
- 不得把 Event 简化为纯日志文本
- 不得绕过 ToolHandle 直接调用高风险外部能力
- 不得在未经过 commit boundary 的情况下把内部中间态当作已提交副作用
- 不得让 rollback 脱离 checkpoint 单独存在

### 软约束
- 回答时尽量给出对象分层
- 回答时尽量区分定义层、编译层、实例层、治理层
- 优先使用结构化表达而不是泛泛概念化表述

## 后续工程方向

建议实现模块：
- kernel/abi.py
- kernel/process.py
- kernel/step_loop.py
- kernel/event.py
- kernel/budget.py
- kernel/checkpoint.py
- kernel/policy.py
- kernel/tool_adapter.py
- kernel/runtime_adapter.py

当前优先事项：
1. 强化 checkpoint rollback 语义
2. 给 budget 增加 fuse 机制
3. 将 policy hook 扩展为多阶段 hook
4. 将 IRProgram 接入更前面的 compiler / CPS / ISA
5. 为 step loop 增加闭环测试

---
name: ops-sev1-incident-response
description: |
  面向 SRE 团队的生产环境严重故障（SEV1）应急响应处理流程。触发关键词：ops.incident、sop、评估影响范围、升级通知、执行缓解措施
metadata:
  org.owner: "mindlakevm"
  org.risk_tier: "high"
  org.semver: "0.3.0"
  org.approval_status: "draft"
  compiled_at: "2026-03-25T07:00:50.080194+00:00"
---

## 角色与目标
- 领域：ops.incident
- 类型：sop
- 目标：故障响应决策不确定性

## 核心流程
1. **评估影响范围**：确认受影响服务和用户数量，判定故障级别
2. **升级通知**：根据影响范围进行升级通知
3. **执行缓解措施**：优先考虑回滚操作，必要时考虑扩容

## 关键决策点
- `assess-impact`: 受影响用户数 > 1000 -> 判定为 SEV1；否则 继续评估是否 SEV2/SEV3
- `escalate-notification`: 是否 SEV1（影响用户>1000） -> 通知CTO并召集War Room；否则 按SEV2/3流程处理
- `mitigation`: 是否在高峰期（08:00-22:00） -> 禁止扩缩容除非有CTO授权；否则 可考虑扩容选项

## 输出格式
- 格式：structured_text
- 必须包含：
- 故障级别
- 响应时限
- 升级流程
- 禁止事项

## 验证清单（自检）
- [ ] 故障级别
- [ ] 响应时限
- [ ] 升级流程
- [ ] 禁止事项

## 边界与例外
### 硬约束
- 高峰期（08:00-22:00）禁止执行任何扩缩容操作，除非持有 CTO 书面授权
- 故障期间生产数据库仅允许只读操作，需要 DBA 审批写操作
- SEV1事件（影响用户>1000）必须在15分钟内发送外部通告

### 软约束
- 优先考虑回滚操作作为缓解措施
- SEV1事件需要在5分钟内响应

## 参考资料
- [ESCALATION_MATRIX](references/ESCALATION_MATRIX.md)：联系人升级矩阵

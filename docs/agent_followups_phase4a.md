# Agent 后续改进清单（Phase 4A 记录，不在本轮修复）

以下问题属于 Agent / Conversation 业务范围，本轮只记录，不修改：

1. 澄清回复可能没有保存到 Conversation History。
2. 拒答和 Hello 等消息可能没有持久化。
3. Hello / Thank you / What can you do 等简单消息缺少自然响应。
4. 推荐问题需要从具体订单问题调整为通用业务问题。
5. 多轮澄清的上下文延续需要检查。

建议由负责 Agent 的组员在独立分支处理，并补充对应测试：

- 澄清回复保存后，刷新会话能恢复完整上下文。
- 拒答/问候是否应进入历史，需要产品决策。
- 推荐问题按角色、当前风险、最近会话动态生成。
- 多轮澄清使用 `original_question` + `clarification_reply` 串联，验证 LangGraph checkpoint。

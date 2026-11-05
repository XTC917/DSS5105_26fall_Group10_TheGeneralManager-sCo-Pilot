"""Deterministic bilingual drafts. No address inference and no delivery side effects."""

from __future__ import annotations

import re
from typing import Literal

from backend.config import factory_date

EmailLanguage = Literal["auto", "zh", "en"]
EmailAudience = Literal["unspecified", "internal", "customer"]


def email_language(language: EmailLanguage, current_text: str) -> str:
    if language != "auto":
        return language
    # The grounding context starts with this turn, followed by older turns.
    # Explicit language requests are passed as zh/en by the agent.
    current_line = current_text.split("\n", 1)[0]
    return "zh" if re.search(r"[\u4e00-\u9fff]", current_line) else "en"


def compose_email(order: dict, flags: list[str], *, language: str,
                  audience: EmailAudience = "unspecified") -> dict:
    zh = language == "zh"
    missing = "未提供" if zh else "not provided"

    def value(key: str) -> str:
        raw = order.get(key)
        return missing if raw is None or raw == "" else str(raw)

    oid = value("order_id")
    completed = order.get("status") == "COMPLETE"
    if zh:
        stages = {"ORDERED": "待生产", "KNITTING": "针织", "ASSEMBLY": "缝合",
                  "WASHING": "洗水", "PACKING": "包装", "COMPLETE": "已完成"}
        statuses = {"IN_PROGRESS": "生产中", "COMPLETE": "已完成", "ORDERED": "已下单"}
        risks = {"OVERDUE": "已逾期", "STALLED": "生产停滞", "TIGHT_DEADLINE": "交期紧张"}
        subject = f"订单 {oid} 的进度通知" if audience == "customer" or completed else f"请跟进订单 {oid} 的生产进度"
        greeting = f"{value('customer')}，您好：" if audience == "customer" else "您好："
        facts = (f"截至工厂业务日期 {factory_date().isoformat()}，订单 {oid}（客户：{value('customer')}，"
                 f"产品：{value('product')}，数量：{value('pieces')} 件）的状态为"
                 f"{statuses.get(order.get('status'), value('status'))}，当前阶段为"
                 f"{stages.get(order.get('current_stage'), value('current_stage'))}。"
                 f"计划交付日期为 {value('due_date')}，最后活动日期为 {value('last_activity_date')}。")
        # Internal rule flags are not sent to customers as unexplained system codes.
        if audience != "customer":
            facts += " 系统风险提示：" + ("、".join(risks.get(f, f) for f in flags) or "未触发风险规则") + "。"
        if audience == "customer":
            action = "如您对该订单有需要确认的事项，请回复告知，以便我们跟进。"
        elif completed:
            action = "系统记录该订单已完成；如需跟进，请确认是否还有交付相关事项。"
        else:
            action = "请协助确认当前进度、是否存在生产阻碍及预计完成时间，以便安排后续工作。"
        body = f"{greeting}\n\n{facts}\n\n{action}\n\n谢谢！\nSweaterCo"
        disclaimer = "仅生成草稿，未发送。收件人及邮箱尚未核实，请补充并核对。"
    else:
        subject = f"Progress update for order {oid}" if audience == "customer" or completed else f"Please follow up on order {oid}"
        greeting = f"Dear {value('customer')}," if audience == "customer" else "Hello,"
        facts = (f"As of the factory business date {factory_date().isoformat()}, order {oid} for {value('customer')} "
                 f"covers {value('pieces')} pieces of {value('product')}. Its recorded status is "
                 f"{value('status')} and current stage is {value('current_stage')}. "
                 f"The scheduled due date is {value('due_date')}; the last recorded activity date "
                 f"is {value('last_activity_date')}.")
        if audience != "customer":
            facts += " Factory rule flags: " + (", ".join(flags) or "none recorded") + "."
        if audience == "customer":
            action = "Please let us know if you have any questions or requirements for this order so we can follow up."
        elif completed:
            action = "The order is recorded as complete. Please confirm whether any delivery matters still require follow-up."
        else:
            action = "Please confirm the current progress, any production blockers, and the estimated completion time so we can plan the next steps."
        body = f"{greeting}\n\n{facts}\n\n{action}\n\nThank you,\nSweaterCo"
        disclaimer = "Draft only, not sent. The recipient and email address have not been verified; please supply and check them."
    return {"to": None, "recipient_name": order.get("customer") if audience == "customer" else None,
            "recipient_status": "missing", "subject": subject, "body": body,
            "language": language, "audience": audience, "disclaimer": disclaimer,
            "template_id": f"{audience}_order_followup_v1", "order_id": order["order_id"],
            "customer": order.get("customer"), "risk_flags": flags}

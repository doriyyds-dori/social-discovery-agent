"""
Dashboard page – full practical operations dashboard.
"""

import streamlit as st
import requests
from collections import Counter
from datetime import date, datetime, timedelta

API = "http://localhost:8000"

st.set_page_config(page_title="数据看板", page_icon="📊", layout="wide")
st.title("📊 数据看板")


def safe_get(endpoint: str) -> list:
    try:
        r = requests.get(f"{API}{endpoint}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


keywords = safe_get("/keywords/")
contents = safe_get("/contents/")
tasks    = safe_get("/tasks/")

# ── 1. 顶部核心概览指标 ────────────────────────────────────────────
st.subheader("📈 核心概览")
pending_tasks   = [t for t in tasks if t.get("status") in ("待处理", "pending")]
processing_tasks = [t for t in tasks if t.get("status") == "处理中"]
done_tasks      = [t for t in tasks if t.get("status") == "已完成"]
high_value_contents = [c for c in contents if c.get("comment_value") == "高"]
priority_contents   = [c for c in contents if c.get("recommended_action") == "优先跟进"]

r1c1, r1c2, r1c3, r1c4, r1c5, r1c6 = st.columns(6)
r1c1.metric("📄 内容总数", len(contents))
r1c2.metric("✅ 任务总数", len(tasks))
r1c3.metric("⏳ 待处理任务", len(pending_tasks) + len(processing_tasks))
r1c4.metric("🎉 已完成任务", len(done_tasks))
r1c5.metric("💬 高评论价值内容", len(high_value_contents))
r1c6.metric("🔥 优先跟进内容", len(priority_contents))

st.markdown("---")

# ── 2–6. 内容分布统计（两行） ──────────────────────────────────────
st.subheader("📊 内容分布统计")

col_left, col_right = st.columns(2)

with col_left:
    # 2. 按来源统计
    st.markdown("**按来源**")
    if contents:
        source_counts = Counter(c.get("source_name") or "未知" for c in contents)
        rows = [{"来源": s, "数量": n} for s, n in sorted(source_counts.items())]
        st.table(rows)
    else:
        st.caption("暂无数据")

    st.markdown("")

    # 4. 按评论价值等级统计
    st.markdown("**按评论价值等级**")
    if contents:
        VALUE_ORDER = ["高", "中", "低", ""]
        cv_counts = Counter(c.get("comment_value") or "未填写" for c in contents)
        rows = [{"评论价值": v if v else "未填写", "数量": cv_counts[v]}
                for v in VALUE_ORDER if v in cv_counts or (not v and "未填写" in cv_counts)]
        if rows:
            st.table(rows)
        else:
            st.caption("暂无数据")
    else:
        st.caption("暂无数据")

with col_right:
    # 3. 按平台统计
    st.markdown("**按平台**")
    if contents:
        platform_counts = Counter(c.get("platform") or "未知" for c in contents)
        rows = [{"平台": p, "数量": n} for p, n in sorted(platform_counts.items())]
        st.table(rows)
    else:
        st.caption("暂无数据")

    st.markdown("")

    # 5. 按推荐动作统计
    st.markdown("**按推荐动作**")
    if contents:
        ACTION_ORDER = ["优先跟进", "仅观察", "暂不处理", ""]
        ac_counts = Counter(c.get("recommended_action") or "未填写" for c in contents)
        rows = [{"推荐动作": a if a else "未填写", "数量": ac_counts[a]}
                for a in ACTION_ORDER if a in ac_counts or (not a and "未填写" in ac_counts)]
        if rows:
            st.table(rows)
        else:
            st.caption("暂无数据")
    else:
        st.caption("暂无数据")

# 6. 按评论关键信号统计（全宽）
st.markdown("**按评论关键信号**")
SIGNAL_LABELS = ["试驾咨询", "价格咨询", "落地价", "竞品对比", "提车周期",
                 "置换政策", "配置咨询", "负面吐槽", "围观无意向", "其他"]
if contents:
    sig_counts = Counter(c.get("comment_signal") or "未填写" for c in contents)
    all_signals = sorted(sig_counts.keys(), key=lambda x: (SIGNAL_LABELS.index(x) if x in SIGNAL_LABELS else 99, x))
    scols = st.columns(max(len(all_signals), 1))
    for i, sig in enumerate(all_signals):
        scols[i].metric(sig or "未填写", sig_counts[sig])
else:
    st.caption("暂无数据")

st.markdown("---")

# ── 7. 按任务状态统计 ──────────────────────────────────────────────
st.subheader("📋 任务状态分布")
if tasks:
    STATUS_ORDER = ["待处理", "处理中", "已完成", "已跳过"]
    status_counts = Counter(t.get("status") or "未知" for t in tasks)
    present = [s for s in STATUS_ORDER if s in status_counts]
    if present:
        tcols = st.columns(len(present))
        for i, s in enumerate(present):
            tcols[i].metric(s, status_counts[s])

    # ── 完成率 ────────────────────────────────────────────────────
    total_tasks = len(tasks)
    done_count = status_counts.get("已完成", 0)
    skipped_count = status_counts.get("已跳过", 0)
    closed_count = done_count + skipped_count
    completion_rate = done_count / total_tasks if total_tasks else 0
    closed_rate    = closed_count / total_tasks if total_tasks else 0

    rate_col1, rate_col2 = st.columns([1, 3])
    rate_col1.metric(
        "🎯 任务完成率",
        f"{completion_rate:.0%}",
        help="已完成任务 ÷ 任务总数",
    )
    with rate_col2:
        st.markdown(f"**进度：已完成 {done_count} / 总计 {total_tasks}**（含跳过共处理 {closed_count} 条，占 {closed_rate:.0%}）")
        st.progress(completion_rate)
else:
    st.caption("暂无任务记录。")

st.markdown("---")

# ── 8. 即将到期任务 ────────────────────────────────────────────────
st.subheader("⏰ 即将到期任务（3天内）")
today = date.today()
deadline = today + timedelta(days=3)
upcoming = []
for t in tasks:
    if t.get("status") in ("已完成", "已跳过"):
        continue
    due = t.get("due_date", "")
    if due:
        try:
            due_date = datetime.strptime(due[:10], "%Y-%m-%d").date()
            if today <= due_date <= deadline:
                upcoming.append(t)
        except Exception:
            pass

if upcoming:
    upcoming.sort(key=lambda t: t.get("due_date", ""))
    rows = [
        {
            "任务编号": t.get("task_number", "—"),
            "任务标题": t.get("title", "—"),
            "负责人": t.get("assignee", "—"),
            "截止时间": t.get("due_date", "—"),
            "当前状态": t.get("status", "—"),
        }
        for t in upcoming
    ]
    st.table(rows)
else:
    st.caption("未来 3 天内无到期任务。")

st.markdown("---")

# ── 9. 高价值待跟进内容 ────────────────────────────────────────────
st.subheader("🔥 高价值待跟进内容")
priority = [
    c for c in contents
    if c.get("recommended_action") == "优先跟进" or c.get("comment_value") == "高"
]
if priority:
    rows = [
        {
            "标题": c.get("title", "—"),
            "平台": c.get("platform", "—"),
            "来源": c.get("source_name", "—"),
            "评论价值": c.get("comment_value", "—"),
            "推荐动作": c.get("recommended_action", "—"),
            "链接": c.get("url", "—"),
        }
        for c in priority[:10]
    ]
    st.table(rows)
else:
    st.caption("暂无高价值或优先跟进内容。")

st.markdown("---")

# ── 10. 最近导入内容 ───────────────────────────────────────────────
st.subheader("🕐 最近导入内容")
if contents:
    recent = sorted(
        contents,
        key=lambda c: c.get("created_at", ""),
        reverse=True,
    )[:8]
    rows = [
        {
            "标题": c.get("title", "—"),
            "平台": c.get("platform", "—"),
            "来源": c.get("source_name", "—"),
            "创建时间": (c.get("created_at", "")[:16].replace("T", " ") if c.get("created_at") else "—"),
        }
        for c in recent
    ]
    st.table(rows)
else:
    st.caption("暂无内容记录。")

"""
Tasks management page.
"""

import streamlit as st
import requests
from datetime import date

API = "http://localhost:8000"

STATUS_OPTIONS = ["待处理", "处理中", "已完成", "已跳过"]
STATUS_EMOJI = {"待处理": "⏳", "处理中": "🔄", "已完成": "✅", "已跳过": "⏭️"}

st.set_page_config(page_title="任务", page_icon="✅", layout="wide")
st.title("✅ 任务")

# ── Fetch existing content for the dropdown ───────────────────────
try:
    contents = requests.get(f"{API}/contents/", timeout=5).json()
except Exception:
    contents = []

content_map = {c["id"]: c["title"] for c in contents}
content_ids = list(content_map.keys())
content_titles = list(content_map.values())

# ── Add new task ──────────────────────────────────────────────────
st.subheader("添加任务")

if not content_titles:
    st.warning("暂无内容记录，请先在「内容」页面添加内容。")
else:
    with st.form("add_task"):
        selected_title = st.selectbox("内容", content_titles)
        assignee = st.text_input("负责人")
        due_date = st.date_input("截止时间", value=date.today())
        description = st.text_area("任务说明")
        submitted = st.form_submit_button("添加")

        if submitted and selected_title:
            idx = content_titles.index(selected_title)
            selected_content_id = content_ids[idx]
            task_title = f"[{selected_title}] {description[:30]}" if description else f"[{selected_title}] 新任务"
            try:
                payload = {
                    "content_id": selected_content_id,
                    "title": task_title,
                    "assignee": assignee,
                    "due_date": str(due_date),
                    "description": description,
                    "status": "待处理",
                }
                r = requests.post(f"{API}/tasks/", json=payload, timeout=5)
                if r.status_code == 200:
                    st.success("任务已添加！")
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "出错"))
            except Exception as e:
                st.error(f"无法连接 API：{e}")

st.markdown("---")

# ── List existing tasks ───────────────────────────────────────────
st.subheader("所有任务")
try:
    tasks = requests.get(f"{API}/tasks/", timeout=5).json()
except Exception:
    tasks = []
    st.warning("无法加载任务。请确认后端是否正在运行。")

# ── Filters ───────────────────────────────────────────────────────
st.markdown("##### 🔍 筛选")
tf1, tf2, tf3 = st.columns(3)
filter_status   = tf1.selectbox("状态", ["全部"] + STATUS_OPTIONS, key="tf_status")
filter_assignee = tf2.text_input("负责人（关键词）", key="tf_assignee")
filter_overdue  = tf3.checkbox("仅显示已超期任务", key="tf_overdue")

filtered_tasks = tasks
if filter_status != "全部":
    filtered_tasks = [t for t in filtered_tasks if t.get("status") == filter_status]
if filter_assignee.strip():
    kw = filter_assignee.strip().lower()
    filtered_tasks = [t for t in filtered_tasks if kw in (t.get("assignee") or "").lower()]
if filter_overdue:
    today_str = date.today().isoformat()
    filtered_tasks = [
        t for t in filtered_tasks
        if t.get("due_date", "") and t.get("due_date", "") < today_str
        and t.get("status") not in ("已完成", "已跳过")
    ]

st.caption(f"共 {len(filtered_tasks)} 条（总计 {len(tasks)} 条）")

# ── View mode toggle ──────────────────────────────────────────────
view_mode = st.radio(
    "视图模式",
    ["📋 列表视图", "🗂️ 看板视图"],
    horizontal=True,
    key="task_view_mode",
    label_visibility="collapsed",
)
st.markdown("---")


def _render_status_change(t: dict, key_suffix: str):
    """Render status selectbox and delete button for a task."""
    cur_status = t["status"]
    cur_idx = STATUS_OPTIONS.index(cur_status) if cur_status in STATUS_OPTIONS else 0
    new_status = st.selectbox(
        "状态",
        STATUS_OPTIONS,
        index=cur_idx,
        key=f"status_{t['id']}_{key_suffix}",
        label_visibility="collapsed",
    )
    if new_status != t["status"]:
        requests.put(
            f"{API}/tasks/{t['id']}",
            json={
                "content_id": t.get("content_id"),
                "title": t["title"],
                "assignee": t.get("assignee", ""),
                "due_date": t.get("due_date", ""),
                "description": t.get("description", ""),
                "status": new_status,
            },
            timeout=5,
        )
        st.rerun()
    if st.button("🗑️", key=f"del_{t['id']}_{key_suffix}", help="删除任务"):
        requests.delete(f"{API}/tasks/{t['id']}", timeout=5)
        st.rerun()


# ── LIST VIEW ─────────────────────────────────────────────────────
if view_mode == "📋 列表视图":
    for t in filtered_tasks:
        emoji = STATUS_EMOJI.get(t["status"], "")
        task_num = t.get("task_number", "")
        header = f"{emoji} {task_num}  {t['title']}" if task_num else f"{emoji} {t['title']}"
        with st.expander(header):
            col_info, col_action = st.columns([5, 2])
            with col_info:
                if t.get("task_number"):
                    st.write(f"**任务编号：** `{t['task_number']}`")
                if t.get("content_title"):
                    st.write(f"**关联内容：** {t['content_title']}")
                if t.get("assignee"):
                    st.write(f"**负责人：** {t['assignee']}")
                if t.get("due_date"):
                    st.write(f"**截止时间：** {t['due_date']}")
                if t.get("description"):
                    st.write(f"**任务说明：** {t['description']}")
                if t.get("completed_at"):
                    st.write(f"**完成时间：** {t['completed_at']}")
            with col_action:
                _render_status_change(t, "list")

# ── KANBAN VIEW ───────────────────────────────────────────────────
else:
    today_str = date.today().isoformat()
    cols = st.columns(4)
    col_headers = ["⏳ 待处理", "🔄 处理中", "✅ 已完成", "⏭️ 已跳过"]
    col_statuses = ["待处理", "处理中", "已完成", "已跳过"]

    for col, header, status in zip(cols, col_headers, col_statuses):
        group = [t for t in filtered_tasks if t.get("status") == status]
        col.markdown(f"**{header}** `{len(group)}`")
        col.markdown("---")
        for t in group:
            task_num = t.get("task_number", "")
            title = t.get("title", "—")
            assignee = t.get("assignee", "")
            due = t.get("due_date", "")

            # Highlight overdue tasks in red
            is_overdue = (
                due and due < today_str and status not in ("已完成", "已跳过")
            )
            card_title = f"🔴 {title}" if is_overdue else title

            with col.expander(card_title[:40] + ("…" if len(card_title) > 40 else ""), expanded=False):
                if task_num:
                    st.caption(f"`{task_num}`")
                if assignee:
                    st.write(f"👤 {assignee}")
                if due:
                    label = f"📅 {due}"
                    if is_overdue:
                        label += " ⚠️ 已超期"
                    st.write(label)
                if t.get("content_title"):
                    st.caption(f"关联：{t['content_title'][:30]}")
                _render_status_change(t, f"kb_{status}")

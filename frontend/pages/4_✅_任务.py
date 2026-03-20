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

for t in tasks:
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
            cur_status = t["status"]
            # Handle legacy English status values gracefully
            if cur_status not in STATUS_OPTIONS:
                cur_idx = 0
            else:
                cur_idx = STATUS_OPTIONS.index(cur_status)

            new_status = st.selectbox(
                "状态",
                STATUS_OPTIONS,
                index=cur_idx,
                key=f"status_{t['id']}",
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

            if st.button("🗑️ 删除", key=f"del_task_{t['id']}"):
                requests.delete(f"{API}/tasks/{t['id']}", timeout=5)
                st.rerun()

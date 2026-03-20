"""
Dashboard page – quick stats overview.
"""

import streamlit as st
import requests

API = "http://localhost:8000"

st.set_page_config(page_title="数据看板", page_icon="📊", layout="wide")
st.title("📊 数据看板")


def safe_get(endpoint: str) -> list:
    """Fetch JSON list from the API; return [] on failure."""
    try:
        r = requests.get(f"{API}{endpoint}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


keywords = safe_get("/keywords/")
contents = safe_get("/contents/")
tasks = safe_get("/tasks/")

col1, col2, col3 = st.columns(3)
col1.metric("🔑 关键词", len(keywords))
col2.metric("📄 内容", len(contents))
col3.metric("✅ 任务", len(tasks))

st.markdown("---")

# Recent content
st.subheader("最近内容")
if contents:
    for item in contents[:5]:
        st.markdown(f"- **{item['title']}** ({item['status']})")
else:
    st.caption("暂无内容。请前往「内容」页面添加。")

# Pending tasks
st.subheader("待办任务")
pending = [t for t in tasks if t["status"] == "pending"]
if pending:
    for t in pending[:5]:
        st.markdown(f"- {t['title']}")
else:
    st.caption("暂无待办任务。")

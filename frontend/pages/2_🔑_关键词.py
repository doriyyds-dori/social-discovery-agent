"""
Keywords management page.
"""

import streamlit as st
import requests

API = "http://localhost:8000"

st.set_page_config(page_title="关键词", page_icon="🔑", layout="wide")
st.title("🔑 关键词")

# ── Add new keyword ───────────────────────────────────────────────
st.subheader("添加关键词")
with st.form("add_keyword"):
    text = st.text_input("关键词")
    platform = st.selectbox("平台", ["通用", "小红书", "抖音", "微博", "知乎", "其他"])
    submitted = st.form_submit_button("添加")
    if submitted and text:
        try:
            r = requests.post(f"{API}/keywords/", json={"text": text, "platform": platform}, timeout=5)
            if r.status_code == 200:
                st.success(f"已添加关键词：{text}")
                st.rerun()
            else:
                st.error(r.json().get("detail", "添加关键词时出错"))
        except Exception as e:
            st.error(f"无法连接 API：{e}")

st.markdown("---")

# ── List existing keywords ────────────────────────────────────────
st.subheader("现有关键词")
try:
    keywords = requests.get(f"{API}/keywords/", timeout=5).json()
except Exception:
    keywords = []
    st.warning("无法加载关键词。请确认后端是否正在运行。")

for kw in keywords:
    col1, col2 = st.columns([4, 1])
    col1.write(f"**{kw['text']}** — _{kw['platform']}_")
    if col2.button("🗑️", key=f"del_kw_{kw['id']}"):
        requests.delete(f"{API}/keywords/{kw['id']}", timeout=5)
        st.rerun()

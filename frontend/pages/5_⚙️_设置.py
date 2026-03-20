"""
Settings page.
"""

import streamlit as st
import requests

API = "http://localhost:8000"

st.set_page_config(page_title="设置", page_icon="⚙️", layout="wide")
st.title("⚙️ 设置")

st.markdown("存储工具使用的简单键值配置。")

# ── Add / update a setting ────────────────────────────────────────
st.subheader("添加或更新设置")
with st.form("upsert_setting"):
    key = st.text_input("键")
    value = st.text_input("值")
    submitted = st.form_submit_button("保存")
    if submitted and key:
        try:
            r = requests.post(f"{API}/settings/", json={"key": key, "value": value}, timeout=5)
            if r.status_code == 200:
                st.success(f"已保存：{key}")
                st.rerun()
            else:
                st.error(r.json().get("detail", "出错"))
        except Exception as e:
            st.error(f"无法连接 API：{e}")

st.markdown("---")

# ── Current settings ──────────────────────────────────────────────
st.subheader("当前设置")
try:
    settings = requests.get(f"{API}/settings/", timeout=5).json()
except Exception:
    settings = []
    st.warning("无法加载设置。请确认后端是否正在运行。")

if settings:
    for s in settings:
        col1, col2, col3 = st.columns([3, 3, 1])
        col1.code(s["key"])
        col2.write(s["value"])
        if col3.button("🗑️", key=f"del_set_{s['id']}"):
            requests.delete(f"{API}/settings/{s['id']}", timeout=5)
            st.rerun()
else:
    st.caption("暂无配置项。")

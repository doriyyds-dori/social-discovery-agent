"""
Social Discovery Agent – Streamlit Frontend
Run with:  streamlit run frontend/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Social Discovery Agent",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Social Discovery Agent")
st.markdown("欢迎！请使用 **侧边栏** 在各页面之间导航。")
st.markdown("---")

st.info(
    "这是一个用于跟踪关键词、发现内容和管理相关任务的内部工具。"
    "请使用侧边栏开始使用。"
)

st.markdown(
    """
    ### 快速导航
    | 页面 | 说明 |
    |------|------|
    | **📊 数据看板** | 总览与快速统计 |
    | **🔑 关键词** | 管理跟踪的关键词 |
    | **📄 内容** | 查看和管理发现的内容 |
    | **✅ 任务** | 跟踪待办事项 |
    | **⚙️ 设置** | 应用配置 |
    """
)

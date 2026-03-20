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

st.markdown("---")

# ── Content source import ─────────────────────────────────────────
st.subheader("📥 内容导入")
st.caption("从内置模拟数据来源导入示例内容记录，用于测试或演示。已存在的内容（相同 URL）将自动跳过。")

if st.button("🚀 导入模拟内容", type="primary"):
    try:
        r = requests.post(f"{API}/sources/mock/import", timeout=10)
        if r.status_code == 200:
            result = r.json()
            st.success(result.get("message", "导入完成"))
            col1, col2, col3 = st.columns(3)
            col1.metric("总数", result.get("total", 0))
            col2.metric("成功导入", result.get("imported", 0))
            col3.metric("已跳过", result.get("skipped", 0))
        else:
            st.error(r.json().get("detail", "导入失败"))
    except Exception as e:
        st.error(f"无法连接 API：{e}")

st.markdown("---")

# ── CSV batch import ──────────────────────────────────────────────
st.subheader("📂 手工批量导入内容")
st.caption("上传 CSV 文件，支持以下列名（中文表头）：平台、标题、链接、摘要、作者、发布时间、原始文本")

uploaded_file = st.file_uploader("选择 CSV 文件", type=["csv"], key="csv_uploader")

if uploaded_file and st.button("📥 开始导入", type="primary", key="csv_import_btn"):
    import csv, io

    # Fetch existing URLs for deduplication
    try:
        existing_contents = requests.get(f"{API}/contents/", timeout=5).json()
        existing_urls = {c.get("url", "") for c in existing_contents if c.get("url")}
    except Exception:
        existing_urls = set()

    raw_bytes = uploaded_file.read()
    # Try common encodings: UTF-8 with BOM, GBK (Windows Chinese), then Latin-1 as fallback
    for enc in ("utf-8-sig", "gbk", "latin-1"):
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        st.error("无法识别文件编码，请将 CSV 另存为 UTF-8 格式后重试。")
        st.stop()
    reader = csv.DictReader(io.StringIO(text))

    COL_MAP = {
        "平台": "platform", "标题": "title", "链接": "url",
        "摘要": "summary", "作者": "author", "发布时间": "published_at",
        "原始文本": "raw_text",
    }

    total = imported = skipped = 0
    errors = []

    for row in reader:
        total += 1
        mapped = {eng: row.get(cn, "").strip() for cn, eng in COL_MAP.items()}
        title = mapped.get("title", "")
        url = mapped.get("url", "")

        if not title:
            errors.append(f"第 {total} 行缺少标题，已跳过")
            skipped += 1
            continue

        if url and url in existing_urls:
            skipped += 1
            continue

        notes_parts = []
        for label, field in [("摘要", "summary"), ("作者", "author"), ("发布时间", "published_at"), ("原文", "raw_text")]:
            val = mapped.get(field, "")
            if val:
                notes_parts.append(f"{label}：{val[:200]}")

        payload = {
            "title": title, "url": url,
            "platform": mapped.get("platform", ""),
            "status": "new",
            "source_name": "手工录入", "source_label": "手工导入",
            "notes": "\n".join(notes_parts),
        }
        try:
            r = requests.post(f"{API}/contents/", json=payload, timeout=5)
            if r.status_code == 200:
                imported += 1
                if url:
                    existing_urls.add(url)
            else:
                errors.append(f"第 {total} 行导入失败：{r.json().get('detail', '未知错误')}")
                skipped += 1
        except Exception as e:
            errors.append(f"第 {total} 行请求失败：{e}")
            skipped += 1

    st.success(f"导入完成：成功 {imported} 条，跳过 {skipped} 条，共 {total} 条。")
    c1, c2, c3 = st.columns(3)
    c1.metric("总数", total)
    c2.metric("成功导入", imported)
    c3.metric("已跳过", skipped)
    if errors:
        with st.expander("⚠️ 导入警告详情"):
            for msg in errors:
                st.write(msg)

st.markdown("---")

# ── Content source registry ───────────────────────────────────────

st.subheader("🗂️ 内容来源列表")
st.caption("当前已注册的内容来源及其接入状态。")

try:
    sources = requests.get(f"{API}/sources/", timeout=5).json()
    STATUS_CN = {"active": "🟢 已接入", "planned": "📋 规划中"}
    TYPE_CN = {"mock": "模拟数据", "manual": "手工导入", "authorized": "授权来源", "third_party": "第三方监测"}
    rows = [
        {
            "名称": s.get("name", "—"),
            "来源类型": TYPE_CN.get(s.get("source_type", ""), s.get("source_type", "—")),
            "状态": STATUS_CN.get(s.get("status", ""), s.get("status", "—")),
            "接入地址": s.get("endpoint") or "—",
        }
        for s in sources
    ]
    st.table(rows)
except Exception as e:
    st.warning(f"无法加载来源列表：{e}")

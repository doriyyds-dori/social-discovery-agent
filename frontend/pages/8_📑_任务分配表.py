"""
任务分配表 (Assignment Table) page.

View, filter, search, delete, and export assignment records.
"""

import streamlit as st
import requests
import pandas as pd

API = "http://localhost:8000"

st.set_page_config(page_title="任务分配表", page_icon="📑", layout="wide")
st.title("📑 任务分配表")


def _fmt_dt(val) -> str:
    if not val:
        return ""
    return str(val).replace("T", " ")[:19]


# ── Fetch filter options ──────────────────────────────────────────
try:
    batches = requests.get(f"{API}/assignments/batches", timeout=5).json()
except Exception:
    batches = []

try:
    departments = requests.get(f"{API}/assignments/departments", timeout=5).json()
except Exception:
    departments = []

# ── Filters ───────────────────────────────────────────────────────
st.subheader("🔍 筛选")
fc1, fc2 = st.columns(2)
filter_batch = fc1.selectbox("批次号", ["全部"] + batches, key="f_batch")
filter_dept = fc2.selectbox("部门", ["全部"] + departments, key="f_dept")

fc3, fc4, fc5 = st.columns(3)
filter_name = fc3.text_input("姓名搜索", key="f_name", placeholder="输入姓名关键词")
filter_eid = fc4.text_input("人员ID搜索", key="f_eid", placeholder="如 EMP-0001")
filter_url = fc5.text_input("链接搜索", key="f_url", placeholder="输入链接关键词")

# ── Fetch assignments ─────────────────────────────────────────────
try:
    assignments = requests.get(f"{API}/assignments/", timeout=10).json()
except Exception:
    assignments = []
    st.warning("无法加载分配记录，请确认后端是否运行。")

# Apply filters
filtered = assignments
if filter_batch != "全部":
    filtered = [a for a in filtered if a.get("batch_number") == filter_batch]
if filter_dept != "全部":
    filtered = [a for a in filtered if a.get("department") == filter_dept]
if filter_name.strip():
    kw = filter_name.strip().lower()
    filtered = [a for a in filtered if kw in (a.get("name") or "").lower()]
if filter_eid.strip():
    kw = filter_eid.strip().upper()
    filtered = [a for a in filtered if kw in (a.get("personnel_eid") or "").upper()]
if filter_url.strip():
    kw = filter_url.strip().lower()
    filtered = [a for a in filtered if kw in (a.get("comment_url") or "").lower()]

st.caption(f"共 {len(filtered)} 条（总计 {len(assignments)} 条）")

# ── Export ────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📤 导出")
ec1, ec2 = st.columns([2, 4])
export_batch = ec1.selectbox("导出批次", ["全部"] + batches, key="export_batch")

export_url = f"{API}/assignments/export-csv"
if export_batch != "全部":
    export_url += f"?batch_number={export_batch}"

# Pre-fetch CSV content so st.download_button works in a single click
csv_data = None
csv_error = None
try:
    r = requests.get(export_url, timeout=10)
    if r.status_code == 200:
        csv_data = r.content
    else:
        csv_error = "导出失败，请确认后端是否正常运行"
except Exception as e:
    csv_error = f"无法连接后端：{e}"

if csv_data is not None:
    filename = f"任务分配表_{export_batch}.csv"
    ec2.download_button(
        label="⬇️ 导出 CSV",
        data=csv_data,
        file_name=filename,
        mime="text/csv",
        key="download_csv",
    )
elif csv_error:
    ec2.warning(csv_error)

# ── Display table ─────────────────────────────────────────────────
st.markdown("---")
st.subheader("分配记录列表")

if filtered:
    df = pd.DataFrame([
        {
            "分配记录ID": a["assignment_id"],
            "批次号": a["batch_number"],
            "内容标题": a.get("content_title", ""),
            "人员ID": a["personnel_eid"],
            "部门": a["department"],
            "姓名": a["name"],
            "评论链接": a.get("comment_url", ""),
            "评论内容": (a.get("comment_text") or "")[:50],
            "创建时间": _fmt_dt(a.get("created_at")),
            "更新时间": _fmt_dt(a.get("updated_at")),
        }
        for a in filtered
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("暂无分配记录。")

# ── Per-record delete ─────────────────────────────────────────────
if filtered:
    st.markdown("---")
    st.subheader("删除记录")
    for a in filtered:
        label = f"{a['assignment_id']}  {a['department']} - {a['name']}  [{a.get('content_title', '')[:30]}]"
        with st.expander(label):
            st.write(f"**批次号：** {a['batch_number']}")
            st.write(f"**内容标题：** {a.get('content_title', '')}")
            st.write(f"**评论链接：** {a.get('comment_url', '')}")
            st.write(f"**评论内容：** {a.get('comment_text', '')}")
            if st.button("🗑️ 删除此记录", key=f"del_{a['id']}"):
                try:
                    r = requests.delete(f"{API}/assignments/{a['id']}", timeout=5)
                    if r.status_code == 200:
                        st.success("记录已删除！")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "删除失败"))
                except Exception as e:
                    st.error(f"无法连接后端：{e}")

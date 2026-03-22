"""
人员名单 (Personnel Roster) management page.
"""

import streamlit as st
import requests
import pandas as pd

API = "http://localhost:8000"

st.set_page_config(page_title="人员名单", page_icon="👥", layout="wide")
st.title("👥 人员名单")

# ── Helper ────────────────────────────────────────────────────────


def _fmt_dt(val) -> str:
    """Format a datetime string to a readable form."""
    if not val:
        return ""
    return str(val).replace("T", " ")[:19]


# ── Fetch departments for filter ──────────────────────────────────
try:
    departments = requests.get(f"{API}/personnel/departments", timeout=5).json()
except Exception:
    departments = []

# ── Add / Edit form ───────────────────────────────────────────────
st.subheader("新增人员")

with st.form("add_personnel", clear_on_submit=True):
    col1, col2 = st.columns(2)
    new_dept = col1.text_input("部门", placeholder="例如：技术部")
    new_name = col2.text_input("姓名", placeholder="例如：张三")
    submitted = st.form_submit_button("➕ 添加")

    if submitted:
        if not new_dept.strip() or not new_name.strip():
            st.error("部门和姓名均为必填项")
        else:
            try:
                r = requests.post(
                    f"{API}/personnel/",
                    json={"department": new_dept.strip(), "name": new_name.strip()},
                    timeout=5,
                )
                if r.status_code == 200:
                    st.success(f"人员已添加！人员ID：{r.json().get('personnel_id', '')}")
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "添加失败"))
            except Exception as e:
                st.error(f"无法连接后端：{e}")

st.markdown("---")

# ── CSV Batch Import ──────────────────────────────────────────────
st.subheader("📥 CSV 批量导入人员名单")
st.caption("CSV 文件需包含中文列头：**部门**、**姓名**。人员ID 由系统自动生成。")

csv_file = st.file_uploader("选择 CSV 文件", type=["csv"], key="csv_upload")

ENCODING_OPTIONS = ["自动识别", "UTF-8", "UTF-8-SIG", "GBK", "GB18030"]
csv_encoding = st.selectbox("文件编码", ENCODING_OPTIONS, index=0, key="csv_encoding")

if csv_file is not None:
    if st.button("📤 开始导入", key="csv_import_btn"):
        enc_param = None if csv_encoding == "自动识别" else csv_encoding.lower()
        try:
            files = {"file": (csv_file.name, csv_file.getvalue(), "text/csv")}
            params = {"encoding": enc_param} if enc_param else {}
            r = requests.post(
                f"{API}/personnel/import-csv",
                files=files,
                params=params,
                timeout=30,
            )
            if r.status_code == 200:
                result = r.json()
                st.success(result.get("message", "导入完成"))
                rc1, rc2, rc3, rc4 = st.columns(4)
                rc1.metric("总数", result.get("total", 0))
                rc2.metric("成功导入", result.get("imported", 0))
                rc3.metric("跳过", result.get("skipped", 0))
                rc4.metric("失败", result.get("failed", 0))
                if result.get("imported", 0) > 0:
                    st.rerun()
            else:
                st.error(r.json().get("detail", "导入失败"))
        except Exception as e:
            st.error(f"无法连接后端：{e}")

st.markdown("---")

# ── Filters ───────────────────────────────────────────────────────
st.subheader("人员列表")
st.markdown("##### 🔍 筛选")
fc1, fc2 = st.columns(2)
filter_dept = fc1.selectbox("部门", ["全部"] + departments, key="filter_dept")
filter_name = fc2.text_input("姓名搜索", key="filter_name", placeholder="输入姓名关键词")

# ── Fetch personnel list ──────────────────────────────────────────
try:
    personnel = requests.get(f"{API}/personnel/", timeout=5).json()
except Exception:
    personnel = []
    st.warning("无法加载人员列表，请确认后端是否正在运行。")

# Apply filters
filtered = personnel
if filter_dept != "全部":
    filtered = [p for p in filtered if p.get("department") == filter_dept]
if filter_name.strip():
    kw = filter_name.strip().lower()
    filtered = [p for p in filtered if kw in (p.get("name") or "").lower()]

st.caption(f"共 {len(filtered)} 条（总计 {len(personnel)} 条）")

# ── Display table ─────────────────────────────────────────────────
if filtered:
    df = pd.DataFrame(
        [
            {
                "人员ID": p["personnel_id"],
                "部门": p["department"],
                "姓名": p["name"],
                "创建时间": _fmt_dt(p.get("created_at")),
                "更新时间": _fmt_dt(p.get("updated_at")),
            }
            for p in filtered
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("暂无人员记录。")

# ── Per-record actions (edit / delete) ────────────────────────────
if filtered:
    st.markdown("---")
    st.subheader("编辑 / 删除")

    for p in filtered:
        label = f"{p['personnel_id']}  {p['department']} - {p['name']}"
        with st.expander(label):
            with st.form(f"edit_{p['id']}"):
                ec1, ec2 = st.columns(2)
                edit_dept = ec1.text_input("部门", value=p["department"], key=f"dept_{p['id']}")
                edit_name = ec2.text_input("姓名", value=p["name"], key=f"name_{p['id']}")
                save_btn = st.form_submit_button("💾 保存修改")

                if save_btn:
                    if not edit_dept.strip() or not edit_name.strip():
                        st.error("部门和姓名均为必填项")
                    else:
                        try:
                            r = requests.put(
                                f"{API}/personnel/{p['id']}",
                                json={"department": edit_dept.strip(), "name": edit_name.strip()},
                                timeout=5,
                            )
                            if r.status_code == 200:
                                st.success("人员信息已更新！")
                                st.rerun()
                            else:
                                st.error(r.json().get("detail", "更新失败"))
                        except Exception as e:
                            st.error(f"无法连接后端：{e}")

            if st.button("🗑️ 删除", key=f"del_{p['id']}", help="删除该人员记录"):
                try:
                    r = requests.delete(f"{API}/personnel/{p['id']}", timeout=5)
                    if r.status_code == 200:
                        st.success("人员已删除！")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "删除失败"))
                except Exception as e:
                    st.error(f"无法连接后端：{e}")

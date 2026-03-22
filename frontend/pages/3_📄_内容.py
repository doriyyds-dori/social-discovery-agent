"""
Contents management page.
"""

import streamlit as st
import requests
from datetime import date

API = "http://localhost:8000"

PLATFORM_OPTIONS = ["", "抖音", "小红书", "视频号", "微博", "其他"]
STATUS_LABELS = {"new": "新建", "reviewed": "已查看", "archived": "已归档"}
VALUE_OPTIONS = ["", "高", "中", "低"]
ACTION_OPTIONS = ["", "优先跟进", "仅观察", "暂不处理"]
SIGNAL_OPTIONS = ["", "试驾咨询", "价格咨询", "落地价", "竞品对比", "提车周期", "置换政策", "配置咨询", "负面吐槽", "围观无意向", "其他"]

st.set_page_config(page_title="内容", page_icon="📄", layout="wide")
st.title("📄 内容")

# ── Add new content ───────────────────────────────────────────────
st.subheader("添加内容")
with st.form("add_content"):
    title = st.text_input("标题")
    url = st.text_input("URL（可选）")
    platform = st.selectbox("平台", PLATFORM_OPTIONS)
    status = st.selectbox("状态", ["new", "reviewed", "archived"], format_func=lambda x: STATUS_LABELS.get(x, x))

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        content_value = st.selectbox("内容价值等级", VALUE_OPTIONS)
    with col_b:
        comment_value = st.selectbox("评论价值等级", VALUE_OPTIONS)
    with col_c:
        recommended_action = st.selectbox("推荐动作", ACTION_OPTIONS)

    comment_signal = st.selectbox("评论关键信号", SIGNAL_OPTIONS)

    notes = st.text_area("备注（可选）")
    submitted = st.form_submit_button("添加")
    if submitted and title:
        try:
            payload = {
                "title": title,
                "url": url,
                "platform": platform,
                "status": status,
                "content_value": content_value,
                "comment_value": comment_value,
                "recommended_action": recommended_action,
                "comment_signal": comment_signal,
                "source_name": "手工录入",
                "source_label": "手工导入",
                "notes": notes,
            }
            r = requests.post(f"{API}/contents/", json=payload, timeout=5)
            if r.status_code == 200:
                st.success(f"已添加：{title}")
                st.rerun()
            else:
                st.error(r.json().get("detail", "出错"))
        except Exception as e:
            st.error(f"无法连接 API：{e}")

st.markdown("---")

# ── List existing content ─────────────────────────────────────────
st.subheader("所有内容")
try:
    contents = requests.get(f"{API}/contents/", timeout=5).json()
except Exception:
    contents = []
    st.warning("无法加载内容。请确认后端是否正在运行。")

# ── Filters ───────────────────────────────────────────────────────
st.markdown("##### 🔍 筛选")
f1, f2, f3, f4 = st.columns(4)
filter_platform = f1.selectbox("平台", PLATFORM_OPTIONS, key="filter_platform")
filter_comment_value = f2.selectbox("评论价值等级", VALUE_OPTIONS, key="filter_cmv")
filter_signal = f3.selectbox("评论关键信号", SIGNAL_OPTIONS, key="filter_signal")
filter_action = f4.selectbox("推荐动作", ACTION_OPTIONS, key="filter_action")

# Dynamic source options derived from loaded records
source_options = [""] + sorted({c.get("source_name", "") for c in contents if c.get("source_name")})
filter_source = st.selectbox("来源", source_options, key="filter_source")

filtered = contents
if filter_platform:
    filtered = [c for c in filtered if c.get("platform") == filter_platform]
if filter_comment_value:
    filtered = [c for c in filtered if c.get("comment_value") == filter_comment_value]
if filter_signal:
    filtered = [c for c in filtered if c.get("comment_signal") == filter_signal]
if filter_action:
    filtered = [c for c in filtered if c.get("recommended_action") == filter_action]
if filter_source:
    filtered = [c for c in filtered if c.get("source_name") == filter_source]

st.caption(f"共 {len(filtered)} 条记录（总计 {len(contents)} 条）")

# ── Default sorting ───────────────────────────────────────────────
_ACTION_ORDER = {"优先跟进": 0, "仅观察": 1, "暂不处理": 2, "": 3}
_VALUE_ORDER = {"高": 0, "中": 1, "低": 2, "": 3}

filtered.sort(key=lambda c: (
    _ACTION_ORDER.get(c.get("recommended_action", ""), 3),
    _VALUE_ORDER.get(c.get("comment_value", ""), 3),
    0 if c.get("created_at") else 1,
    "" if c.get("created_at") else "9",  # missing dates sort last
), reverse=False)
# Reverse created_at within equal groups: re-sort stably by time desc
filtered.sort(key=lambda c: c.get("created_at", ""), reverse=True)
# Re-apply primary sorts (stable sort preserves time order within ties)
filtered.sort(key=lambda c: (
    _ACTION_ORDER.get(c.get("recommended_action", ""), 3),
    _VALUE_ORDER.get(c.get("comment_value", ""), 3),
))

st.markdown("---")

# ── Batch selection area ──────────────────────────────────────────
st.markdown("##### ☑️ 批量操作")

# Initialize selection state
if "batch_selected_ids" not in st.session_state:
    st.session_state["batch_selected_ids"] = set()
if "show_batch_form" not in st.session_state:
    st.session_state["show_batch_form"] = False

filtered_ids = [item["id"] for item in filtered]

sel_col1, sel_col2, sel_col3 = st.columns([2, 2, 6])
if sel_col1.button("全选当前列表"):
    st.session_state["batch_selected_ids"] = set(filtered_ids)
    st.rerun()
if sel_col2.button("取消全选"):
    st.session_state["batch_selected_ids"] = set()
    st.session_state["show_batch_form"] = False
    st.rerun()

selected_ids: set = st.session_state["batch_selected_ids"]
# Keep only ids that are still in the current filtered list
selected_ids &= set(filtered_ids)
st.session_state["batch_selected_ids"] = selected_ids

n_selected = len(selected_ids)

if n_selected > 0:
    st.info(f"已选 **{n_selected}** 条记录")
    if st.button("📋 批量创建任务", type="primary"):
        st.session_state["show_batch_form"] = True

    if st.session_state.get("show_batch_form"):
        st.markdown("##### 📝 批量创建任务 — 共享字段")
        # 取消按钮放在 form 外面，避免 Streamlit 将其当作表单提交触发
        if st.button("✖ 取消", key="cancel_batch"):
            st.session_state["show_batch_form"] = False
            st.rerun()

        with st.form("batch_task_form"):
            bt_assignee = st.text_input("负责人")
            bt_due = st.date_input("截止时间", value=date.today())
            bt_desc = st.text_area("任务说明")
            bt_submit = st.form_submit_button("✅ 确认批量创建")

            if bt_submit:
                payload = {
                    "content_ids": list(selected_ids),
                    "assignee": bt_assignee,
                    "due_date": str(bt_due),
                    "description": bt_desc,
                }
                try:
                    r = requests.post(f"{API}/tasks/batch", json=payload, timeout=10)
                    if r.status_code == 200:
                        result = r.json()
                        msg = result.get("message", "")
                        created = result.get("created", 0)
                        nums = result.get("task_numbers", [])

                        if created > 0:
                            st.success(f"✅ {msg}")
                            if nums:
                                st.write("**已创建任务编号：**")
                                for n in nums:
                                    st.write(f"- {n}")
                        else:
                            st.warning(f"⚠️ {msg}")

                        # Reset selection and form
                        st.session_state["batch_selected_ids"] = set()
                        st.session_state["show_batch_form"] = False
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "批量创建失败"))
                except Exception as e:
                    st.error(f"无法连接 API：{e}")
else:
    st.caption("在下方记录中勾选内容后，此处将显示批量操作按钮。")

st.markdown("---")

# ── Content list (with per-item checkboxes) ───────────────────────
for item in filtered:
    item_id = item["id"]
    is_selected = item_id in st.session_state["batch_selected_ids"]

    # Checkbox + expander header in same row
    cb_col, exp_col = st.columns([1, 20])
    with cb_col:
        checked = st.checkbox("选", value=is_selected, key=f"sel_{item_id}", label_visibility="collapsed")
        if checked and item_id not in st.session_state["batch_selected_ids"]:
            st.session_state["batch_selected_ids"].add(item_id)
            st.rerun()
        elif not checked and item_id in st.session_state["batch_selected_ids"]:
            st.session_state["batch_selected_ids"].discard(item_id)
            st.rerun()

    with exp_col:
        with st.expander(f"{item['title']}  [{STATUS_LABELS.get(item['status'], item['status'])}]"):
            if item.get("url"):
                st.markdown(f"🔗 [{item['url']}]({item['url']})")
            st.write(f"**平台：** {item.get('platform', '—')}")
            if item.get("source_name"):
                st.write(f"**来源：** {item['source_name']}")
            if item.get("author"):
                st.write(f"**作者：** {item['author']}")
            if item.get("published_at"):
                st.write(f"**发布时间：** {item['published_at']}")
            if item.get("summary"):
                st.write(f"**摘要：** {item['summary']}")
            if item.get("raw_text"):
                with st.expander("📝 原始文本"):
                    st.write(item["raw_text"])
            if item.get("notes"):
                st.write(f"**备注：** {item['notes']}")

            if item.get("comment_signal"):
                st.write(f"**评论关键信号：** {item['comment_signal']}")

            # ── Inline edit for evaluation fields ─────────────────
            st.markdown("##### 评估信息")
            with st.form(key=f"edit_content_{item_id}"):
                ec1, ec2, ec3 = st.columns(3)
                cur_cv = item.get("content_value") or ""
                cur_cmv = item.get("comment_value") or ""
                cur_ra = item.get("recommended_action") or ""

                new_cv = ec1.selectbox(
                    "内容价值等级",
                    VALUE_OPTIONS,
                    index=VALUE_OPTIONS.index(cur_cv) if cur_cv in VALUE_OPTIONS else 0,
                    key=f"cv_{item_id}",
                )
                new_cmv = ec2.selectbox(
                    "评论价值等级",
                    VALUE_OPTIONS,
                    index=VALUE_OPTIONS.index(cur_cmv) if cur_cmv in VALUE_OPTIONS else 0,
                    key=f"cmv_{item_id}",
                )
                new_ra = ec3.selectbox(
                    "推荐动作",
                    ACTION_OPTIONS,
                    index=ACTION_OPTIONS.index(cur_ra) if cur_ra in ACTION_OPTIONS else 0,
                    key=f"ra_{item_id}",
                )

                cur_cs = item.get("comment_signal") or ""
                new_cs = st.selectbox(
                    "评论关键信号",
                    SIGNAL_OPTIONS,
                    index=SIGNAL_OPTIONS.index(cur_cs) if cur_cs in SIGNAL_OPTIONS else 0,
                    key=f"cs_{item_id}",
                )

                btn_col1, btn_col2 = st.columns([1, 1])
                save_clicked = btn_col1.form_submit_button("💾 保存评估")
                if save_clicked:
                    update_payload = {
                        "title": item["title"],
                        "url": item.get("url", ""),
                        "platform": item.get("platform", ""),
                        "status": item.get("status", "new"),
                        "content_value": new_cv,
                        "comment_value": new_cmv,
                        "recommended_action": new_ra,
                        "comment_signal": new_cs,
                        "notes": item.get("notes", ""),
                    }
                    try:
                        r = requests.put(f"{API}/contents/{item_id}", json=update_payload, timeout=5)
                        if r.status_code == 200:
                            st.success("评估已更新！")
                            st.rerun()
                        else:
                            st.error(r.json().get("detail", "更新失败"))
                    except Exception as e:
                        st.error(f"无法连接 API：{e}")

            # ── One-click task creation ──────────────────────────────
            st.markdown("##### ✅ 一键创建任务")
            with st.form(key=f"quick_task_{item_id}"):
                qt_assignee = st.text_input("负责人", key=f"qt_assignee_{item_id}")
                qt_due = st.date_input("截止时间", value=date.today(), key=f"qt_due_{item_id}")
                qt_desc = st.text_area("任务说明", key=f"qt_desc_{item_id}")
                qt_submit = st.form_submit_button("✅ 创建任务")
                if qt_submit:
                    task_title = f"[{item['title']}] {qt_desc[:30]}" if qt_desc else f"[{item['title']}] 新任务"
                    task_payload = {
                        "content_id": item_id,
                        "title": task_title,
                        "assignee": qt_assignee,
                        "due_date": str(qt_due),
                        "description": qt_desc,
                        "status": "待处理",
                    }
                    try:
                        r = requests.post(f"{API}/tasks/", json=task_payload, timeout=5)
                        if r.status_code == 200:
                            task_num = r.json().get("task_number", "")
                            st.success(f"任务已创建！编号：{task_num}")
                            st.rerun()
                        else:
                            st.error(r.json().get("detail", "创建失败"))
                    except Exception as e:
                        st.error(f"无法连接 API：{e}")

            if st.button("🗑️ 删除", key=f"del_content_{item_id}"):
                requests.delete(f"{API}/contents/{item_id}", timeout=5)
                st.rerun()

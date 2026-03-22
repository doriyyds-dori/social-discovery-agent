"""
批量任务分配 (Batch Assignment) page.

Allows admin to select content, set target comment counts,
and batch-assign comment tasks to personnel.
"""

import streamlit as st
import requests
import pandas as pd

API = "http://localhost:8000"

st.set_page_config(page_title="批量任务分配", page_icon="📋", layout="wide")
st.title("📋 批量任务分配")

# ── Load content list ─────────────────────────────────────────────
try:
    contents = requests.get(f"{API}/contents/", timeout=5).json()
except Exception:
    contents = []
    st.warning("无法加载内容列表，请确认后端是否运行。")

if not contents:
    st.info("暂无内容记录，请先在「内容」页面添加内容。")
    st.stop()

# Build a display table for selection
content_options = []
for c in contents:
    content_options.append({
        "id": c["id"],
        "标题": c.get("title", ""),
        "平台": c.get("platform", ""),
        "来源": c.get("source_name", ""),
        "评论价值": c.get("comment_value", ""),
        "推荐动作": c.get("recommended_action", ""),
        "链接": c.get("url", ""),
    })

df_contents = pd.DataFrame(content_options)

# ── Step 1: Select contents ───────────────────────────────────────
st.subheader("① 选择待分配内容")

st.dataframe(df_contents, use_container_width=True, hide_index=True)

# Use id|title keys to avoid duplicate-title collision
label_to_id = {f"{c['id']} | {c.get('title', '')[:40]}": c["id"] for c in contents}
label_to_title = {f"{c['id']} | {c.get('title', '')[:40]}": c.get("title", "") for c in contents}
selected_labels = st.multiselect(
    "选择内容（可多选）",
    options=list(label_to_id.keys()),
    key="select_contents",
    placeholder="请选择内容…",
)

selected_ids = [label_to_id[lbl] for lbl in selected_labels]

if not selected_ids:
    st.info("请先选择至少一条内容。")
    st.stop()

st.markdown("---")

# ── Step 2: Set target counts ─────────────────────────────────────
st.subheader("② 设置每条内容的目标评论数")

default_count = st.number_input(
    "统一目标评论数（可在下方逐条修改）",
    min_value=1,
    value=3,
    step=1,
    key="default_count",
)

target_counts = {}
for lbl in selected_labels:
    cid = label_to_id[lbl]
    short_title = label_to_title[lbl][:40] + ("…" if len(label_to_title[lbl]) > 40 else "")
    target_counts[cid] = st.number_input(
        f"{short_title}",
        min_value=1,
        value=int(default_count),
        step=1,
        key=f"target_{cid}",
    )

st.markdown("---")

# ── Step 3: Comment source mode ───────────────────────────────────
st.subheader("③ 评论内容来源方式")

source_modes = ["手动填写统一评论内容", "从评论生成草稿中分配"]
source_mode = st.radio("选择评论内容来源", source_modes, horizontal=True, key="source_mode")

comment_text = ""
if source_mode == "手动填写统一评论内容":
    comment_text = st.text_area(
        "评论内容模板",
        placeholder="请输入本批次的统一评论内容……",
        key="comment_text",
        height=120,
    )
else:
    st.info("将自动使用评论生成中心中「未使用」且「生成成功」的草稿。每个人分配不同的草稿内容。")
    # Show available draft count per selected content
    try:
        drafts = requests.get(f"{API}/comment-drafts/", timeout=5).json()
    except Exception:
        drafts = []
    if drafts and selected_ids:
        draft_info = []
        for cid in selected_ids:
            avail = [d for d in drafts
                     if d.get("content_id") == cid
                     and d.get("usage_status") == "未使用"
                     and d.get("status") == "生成成功"]
            title = label_to_title.get(
                next((lbl for lbl, i in label_to_id.items() if i == cid), ""), str(cid)
            )
            target = target_counts.get(cid, 3)
            status = "✅ 充足" if len(avail) >= target else "⚠️ 不足"
            draft_info.append({
                "内容标题": (title or "")[:40],
                "目标评论数": target,
                "可用草稿数": len(avail),
                "状态": status,
            })
        st.caption("各内容可用草稿情况：")
        st.table(draft_info)

st.markdown("---")

# ── Step 4: Execute ───────────────────────────────────────────────
st.subheader("④ 执行分配")

# Show personnel count for reference
try:
    personnel = requests.get(f"{API}/personnel/", timeout=5).json()
    st.caption(f"当前人员池：{len(personnel)} 人")
except Exception:
    personnel = []
    st.caption("无法获取人员数量")

if st.button("🚀 执行批量分配", type="primary", key="execute_btn"):
    # Validation
    if source_mode == "手动填写统一评论内容" and not comment_text.strip():
        st.error("评论内容不能为空")
    else:
        targets = [
            {"content_id": cid, "target_count": tc}
            for cid, tc in target_counts.items()
        ]
        payload = {
            "targets": targets,
            "comment_source_mode": "manual" if source_mode == "手动填写统一评论内容" else "draft",
            "comment_text": comment_text.strip() if source_mode == "手动填写统一评论内容" else "",
        }
        try:
            r = requests.post(
                f"{API}/assignments/batch",
                json=payload,
                timeout=30,
            )
            if r.status_code == 200:
                result = r.json()
                if result.get("failed_count", 0) == 0:
                    st.success(result.get("message", "分配完成"))
                else:
                    st.warning(result.get("message", "部分分配完成"))

                # Summary metrics
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("选中内容数", result.get("selected_count", 0))
                mc2.metric("成功分配", result.get("success_count", 0))
                mc3.metric("失败", result.get("failed_count", 0))
                mc4.metric("生成记录数", result.get("total_records", 0))

                st.caption(f"批次号：**{result.get('batch_number', '')}**")

                # Per-content detail table
                details = result.get("details", [])
                if details:
                    st.markdown("##### 逐条分配明细")
                    detail_df = pd.DataFrame([
                        {
                            "内容标题": d.get("content_title", ""),
                            "链接": d.get("content_url", ""),
                            "目标评论数": d.get("target_count", 0),
                            "实际分配数": d.get("assigned_count", 0),
                            "结果": d.get("result", ""),
                            "失败原因": d.get("reason", ""),
                        }
                        for d in details
                    ])
                    st.dataframe(detail_df, use_container_width=True, hide_index=True)
            else:
                st.error(r.json().get("detail", "分配失败"))
        except Exception as e:
            st.error(f"无法连接后端：{e}")


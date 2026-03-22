"""
评论生成中心 — Comment Generation Center.

Generate comment drafts using LLM, with optional manual editing.
"""

import streamlit as st
import requests

API = "http://localhost:8000"

st.set_page_config(page_title="评论生成中心", page_icon="💬", layout="wide")
st.title("💬 评论生成中心")
st.caption("选择内容 → 设置生成策略 → 大模型批量生成不同评论草稿 → （可选编辑）→ 后续进入批量任务分配")

# ── Step 1: 选择内容 ──────────────────────────────────────────────
st.subheader("① 选择内容")

try:
    contents = requests.get(f"{API}/contents/", timeout=5).json()
except Exception:
    contents = []
    st.warning("无法加载内容列表。")

if not contents:
    st.info("暂无可用内容。请先在内容页添加内容。")
    st.stop()

content_options = {f"{c['id']} | {c.get('title', '—')[:40]}": c for c in contents}
selected_labels = st.multiselect("选择要生成评论的内容（可多选）", list(content_options.keys()), placeholder="请选择内容…")
selected_contents = [content_options[lbl] for lbl in selected_labels]

if not selected_contents:
    st.info("请先在上方选择至少一条内容。")

# ── Step 2: 生成策略 ─────────────────────────────────────────────
st.markdown("---")
st.subheader("② 生成策略设置")

STYLES = ["真实用户口吻", "理性分析", "轻松交流", "简洁直接"]
TONES = ["中性", "正向", "轻微种草", "提问式"]
LENGTHS = ["简短", "适中", "较长"]

col_a, col_b = st.columns(2)
gen_topic = col_a.text_input("评论主题", placeholder="例：试驾体验、性价比讨论")
gen_requirements = col_b.text_input("生成要求", placeholder="例：不要提竞品名称")

col1, col2, col3, col4 = st.columns(4)
gen_style = col1.selectbox("风格", STYLES)
gen_tone = col2.selectbox("语气", TONES)
gen_length = col3.selectbox("字数要求", LENGTHS)
gen_count = col4.number_input("每条内容生成评论数", min_value=1, max_value=20, value=3, step=1)

gen_diversified = st.checkbox("允许差异化表达（推荐开启，生成更自然多样的评论）", value=True)

# Mock switch — explicit, not silent
use_mock = st.checkbox(
    "⚠️ 使用 Mock 测试生成（不调用真实大模型，仅用于功能测试）",
    value=False,
    help="勾选后将使用内置模板生成测试评论，不消耗 API 额度。不勾选时将使用「设置 → 大模型配置」中的默认模型。",
)

if use_mock:
    st.warning("⚠️ 当前为 **Mock 测试模式**，生成内容来自内置模板，不是真实大模型输出。请勿将测试生成内容用于正式场景。")

# ── Step 3: 执行生成 ─────────────────────────────────────────────
st.markdown("---")
st.subheader("③ 执行生成")

if selected_contents:
    # Per-content target table
    st.caption("以下为选中内容的目标生成数：")
    target_data = []
    for c in selected_contents:
        target_data.append({
            "内容ID": c["id"],
            "标题": c.get("title", "—")[:50],
            "目标评论数": gen_count,
        })
    st.table(target_data)

if st.button("🚀 开始生成评论草稿", type="primary", disabled=len(selected_contents) == 0):
    targets = [{"content_id": c["id"], "target_count": gen_count} for c in selected_contents]
    payload = {
        "targets": targets,
        "topic": gen_topic,
        "requirements": gen_requirements,
        "style": gen_style,
        "tone": gen_tone,
        "length_req": gen_length,
        "diversified": gen_diversified,
        "use_mock": use_mock,
    }
    with st.spinner("正在生成评论草稿，请稍候…"):
        try:
            r = requests.post(f"{API}/comment-drafts/generate", json=payload, timeout=120)
            if r.status_code == 200:
                result = r.json()
                # Summary
                mode_label = "Mock 测试" if result["generation_mode"] == "mock" else f"大模型（{result.get('llm_info', '')}）"
                if result["failed_count"] == 0 and result["partial_count"] == 0:
                    st.success(f"✅ {result['message']}")
                elif result["success_count"] > 0 or result["partial_count"] > 0:
                    st.warning(f"⚠️ {result['message']}")
                else:
                    st.error(f"❌ {result['message']}")

                mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                mc1.metric("选中内容", result["selected_count"])
                mc2.metric("成功", result["success_count"])
                mc3.metric("部分成功", result["partial_count"])
                mc4.metric("失败", result["failed_count"])
                mc5.metric("生成草稿", result["total_drafts"])

                st.info(f"📋 批次号：**{result['batch_number']}** | 生成方式：**{mode_label}**")

                # Per-content detail
                with st.expander("📊 逐条内容生成明细"):
                    detail_rows = []
                    for d in result.get("details", []):
                        detail_rows.append({
                            "内容标题": d["content_title"][:40],
                            "内容链接": d.get("content_url", ""),
                            "目标生成数": d["target_count"],
                            "实际生成数": d["actual_count"],
                            "结果": d["result"],
                            "原因": d.get("reason", ""),
                        })
                    st.table(detail_rows)

                st.rerun()
            else:
                detail = r.json().get("detail", "生成失败")
                st.error(f"❌ {detail}")
        except Exception as e:
            st.error(f"请求失败：{e}")

# ── Step 4: 草稿列表 ─────────────────────────────────────────────
st.markdown("---")
st.subheader("④ 已生成草稿列表")

try:
    drafts = requests.get(f"{API}/comment-drafts/", timeout=5).json()
except Exception:
    drafts = []
    st.warning("无法加载草稿列表。")

if not drafts:
    st.caption("暂无草稿。请先在上方生成评论草稿。")
else:
    # Filters
    batches = sorted(set(d["batch_number"] for d in drafts), reverse=True)
    filter_batch = st.selectbox("按批次筛选", ["全部"] + batches, key="filter_batch")
    statuses = ["全部", "生成成功", "生成失败", "待处理"]
    filter_status = st.selectbox("按状态筛选", statuses, key="filter_status")

    filtered = drafts
    if filter_batch != "全部":
        filtered = [d for d in filtered if d["batch_number"] == filter_batch]
    if filter_status != "全部":
        filtered = [d for d in filtered if d["status"] == filter_status]

    st.caption(f"共 {len(filtered)} 条草稿")

    for d in filtered:
        d_id = d["id"]
        mode_icon = "🤖" if d["generation_mode"] == "real_llm" else "🧪"
        status_icon = {"生成成功": "✅", "生成失败": "❌", "待处理": "⏳"}.get(d["status"], "")
        edited_tag = " ✏️已编辑" if d.get("is_edited") else ""
        usage_tag = f" [{d.get('usage_status', '未使用')}]"
        label = (
            f"{status_icon} {mode_icon} {d['draft_id']} | "
            f"{d['content_title'][:30]} | {d['status']}{edited_tag}{usage_tag}"
        )

        with st.expander(label):
            st.write(f"**草稿ID：** {d['draft_id']}")
            st.write(f"**批次号：** {d['batch_number']}")
            st.write(f"**内容标题：** {d['content_title']}")
            st.write(f"**评论链接：** {d.get('comment_url') or '—'}")
            st.write(f"**评论主题：** {d.get('topic') or '—'}")
            st.write(f"**生成要求：** {d.get('requirements') or '—'}")
            st.write(f"**风格：** {d.get('style', '')} | **语气：** {d.get('tone', '')} | **字数：** {d.get('length_req', '')}")
            st.write(f"**生成方式：** {'大模型' if d['generation_mode'] == 'real_llm' else 'Mock 测试'} ({d.get('llm_provider', '')} / {d.get('llm_model', '')})")
            st.write(f"**使用状态：** {d.get('usage_status', '未使用')}")
            st.write(f"**生成状态：** {d['status']}")

            if d.get("error_message"):
                st.error(f"错误信息：{d['error_message']}")

            # Editable comment text
            st.markdown("**评论内容：**")
            new_text = st.text_area(
                "编辑评论内容",
                value=d.get("comment_text", ""),
                key=f"edit_text_{d_id}",
                label_visibility="collapsed",
            )

            btn_c1, btn_c2 = st.columns(2)
            if btn_c1.button("💾 保存修改", key=f"save_{d_id}"):
                if new_text != d.get("comment_text", ""):
                    try:
                        r = requests.put(
                            f"{API}/comment-drafts/{d_id}",
                            json={"comment_text": new_text},
                            timeout=5,
                        )
                        if r.status_code == 200:
                            st.success("保存成功！")
                            st.rerun()
                        else:
                            st.error("保存失败")
                    except Exception as e:
                        st.error(f"请求失败：{e}")
                else:
                    st.info("内容未变更。")

            if btn_c2.button("🗑️ 删除", key=f"del_draft_{d_id}"):
                try:
                    requests.delete(f"{API}/comment-drafts/{d_id}", timeout=5)
                    st.success("草稿已删除！")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败：{e}")

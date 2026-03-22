"""
Settings page.
"""

import streamlit as st
import requests
import json

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

# ── LLM Config ────────────────────────────────────────────────────
st.subheader("🤖 大模型配置")
st.caption("配置和管理大模型 API，用于评论生成等场景。测试连接前请先安装对应 SDK（pip install openai / anthropic）。")

# Fetch provider metadata
try:
    _prov_meta = requests.get(f"{API}/llm-configs/providers", timeout=5).json()
    _PROVIDERS = _prov_meta.get("providers", [])
    _PROTOCOLS = _prov_meta.get("protocols", [])
    _DEFAULT_URLS = _prov_meta.get("default_base_urls", {})
except Exception:
    _PROVIDERS = ["OpenAI", "Gemini", "Claude", "千问", "DeepSeek", "豆包", "自定义兼容接口"]
    _PROTOCOLS = ["openai_compatible", "native"]
    _DEFAULT_URLS = {}

_PROT_DEFAULTS = {
    "OpenAI": "openai_compatible", "Gemini": "openai_compatible",
    "Claude": "native", "千问": "openai_compatible",
    "DeepSeek": "openai_compatible", "豆包": "openai_compatible",
    "自定义兼容接口": "openai_compatible",
}
_PURPOSES = ["评论生成", "备用", "测试"]
_PROT_LABELS = {"openai_compatible": "OpenAI 兼容", "native": "原生 SDK"}

# -- Add new config --
st.markdown("##### ➕ 新增大模型配置")
llm_provider = st.selectbox("服务商", _PROVIDERS, key="llm_add_provider")
default_prot = _PROT_DEFAULTS.get(llm_provider, "openai_compatible")
default_url = _DEFAULT_URLS.get(llm_provider, "")

with st.form("add_llm_config"):
    llm_model = st.text_input("模型名称", placeholder="例：gpt-4o / gemini-2.0-flash / deepseek-chat")
    llm_key = st.text_input("API Key", type="password")
    llm_url = st.text_input("Base URL", value=default_url, placeholder="留空则使用默认地址")
    llm_prot = st.selectbox("接入方式", _PROTOCOLS, index=_PROTOCOLS.index(default_prot) if default_prot in _PROTOCOLS else 0,
                            format_func=lambda x: _PROT_LABELS.get(x, x))
    lc1, lc2, lc3 = st.columns(3)
    llm_enabled = lc1.checkbox("启用", value=True)
    llm_default = lc2.checkbox("设为默认（评论生成）", value=False)
    llm_purpose = lc3.selectbox("用途", _PURPOSES)
    llm_notes = st.text_input("备注", placeholder="可选，例：公司正式账号")
    if st.form_submit_button("✅ 保存配置"):
        if not llm_model.strip():
            st.error("模型名称不能为空")
        elif not llm_key.strip():
            st.error("API Key 不能为空")
        else:
            try:
                payload = {
                    "provider": llm_provider, "model_name": llm_model.strip(),
                    "api_key": llm_key.strip(), "base_url": llm_url.strip(),
                    "protocol": llm_prot, "enabled": llm_enabled,
                    "is_default": llm_default, "purpose": llm_purpose,
                    "notes": llm_notes.strip(),
                }
                r = requests.post(f"{API}/llm-configs/", json=payload, timeout=5)
                if r.status_code == 200:
                    st.success("配置已保存！")
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "保存失败"))
            except Exception as e:
                st.error(f"无法连接后端：{e}")

# -- List existing configs --
st.markdown("##### 📋 当前大模型配置列表")
try:
    llm_configs = requests.get(f"{API}/llm-configs/", timeout=5).json()
except Exception:
    llm_configs = []
    st.warning("无法加载大模型配置。")

if not llm_configs:
    st.caption("暂无配置，请在上方新增。")
else:
    for cfg in llm_configs:
        cfg_id = cfg["id"]
        enabled_tag = "✅" if cfg["enabled"] else "⛔"
        default_tag = " ⭐默认" if cfg["is_default"] else ""
        label = f"{enabled_tag} {cfg['provider']} / {cfg['model_name']}{default_tag}  [{cfg.get('purpose', '')}]"

        with st.expander(label):
            st.write(f"**服务商：** {cfg['provider']}")
            st.write(f"**模型名称：** {cfg['model_name']}")
            st.write(f"**API Key：** `{cfg['api_key_masked']}`")
            st.write(f"**Base URL：** {cfg.get('base_url') or '（默认）'}")
            st.write(f"**接入方式：** {_PROT_LABELS.get(cfg.get('protocol', ''), cfg.get('protocol', ''))}")
            st.write(f"**用途：** {cfg.get('purpose', '')}")
            st.write(f"**备注：** {cfg.get('notes') or '—'}")

            btn_col1, btn_col2 = st.columns(2)
            # Test connection
            if btn_col1.button("🔗 测试连接", key=f"test_llm_{cfg_id}"):
                with st.spinner("正在测试连接…"):
                    try:
                        r = requests.post(f"{API}/llm-configs/{cfg_id}/test", timeout=30)
                        result = r.json()
                        if result.get("success"):
                            st.success(result.get("message", "连接成功"))
                        else:
                            st.error(result.get("message", "连接失败"))
                    except Exception as e:
                        st.error(f"测试失败：{e}")

            # Delete
            if btn_col2.button("🗑️ 删除", key=f"del_llm_{cfg_id}"):
                try:
                    requests.delete(f"{API}/llm-configs/{cfg_id}", timeout=5)
                    st.success("配置已删除！")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败：{e}")

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
    TYPE_CN = {
        "mock": "模拟数据", "douyin_keyword": "抖音关键词搜索",
        "manual": "手工导入", "authorized": "授权来源", "third_party": "第三方监测",
    }
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

st.markdown("---")

# ── Sync config management ────────────────────────────────────────
st.subheader("🔄 来源同步任务配置")
st.caption("管理未来真实内容同步任务的配置信息。当前状态由系统维护，暂不执行真实同步。")

SYNC_MODE_OPTIONS = ["手动", "定时"]
STATUS_BADGE = {
    "未执行": "⬜ 未执行",
    "空闲": "🟢 空闲",
    "执行中": "🔵 执行中",
    "执行失败": "🔴 执行失败",
}

# ── Create new sync config ────────────────────────────────────────
# Fetch available source names from registry API for the selectbox
try:
    _source_registry = requests.get(f"{API}/sources/", timeout=5).json()
    _SOURCE_OPTIONS = [s["name"] for s in _source_registry if s.get("name")]
except Exception:
    _SOURCE_OPTIONS = ["模拟数据", "抖音关键词搜索"]  # 回退默认值

st.markdown("##### ➕ 新建同步任务配置")

# Source selectbox OUTSIDE the form so changing it triggers an immediate rerun,
# allowing conditional Douyin-specific fields to appear/disappear dynamically.
sc_source = st.selectbox("来源", options=_SOURCE_OPTIONS, key="new_sc_source")

with st.form("add_sync_config"):
    sc_name = st.text_input("任务名称", placeholder="例：小红书-试驾咨询监控")

    # ── 来源专属字段 ────────────────────────────────────────────
    if sc_source == "抖音关键词搜索":
        st.caption("ℹ️ 以下为抖音关键词搜索专属参数，当前仅作结构预留，尚未接入真实执行。")
        dy_keyword = st.text_input("抖音关键词", placeholder="例：途观L 试驾")
        dy_col1, dy_col2, dy_col3 = st.columns(3)
        dy_count = dy_col1.number_input("每次拉取条数", min_value=1, max_value=50, value=10, step=1)
        dy_cursor = dy_col2.number_input("游标", min_value=0, value=0, step=1)
        dy_comments = dy_col3.checkbox("是否拉取评论", value=False)
        sc_keywords = ""  # 抖音来源不使用通用关键词，避免双重真相
    else:
        sc_keywords = st.text_input("关键词（逗号分隔）", placeholder="例：试驾,价格咨询,落地价")

    sc_col1, sc_col2 = st.columns(2)
    sc_mode = sc_col1.selectbox("同步方式", SYNC_MODE_OPTIONS)
    sc_enabled = sc_col2.checkbox("是否启用", value=True)
    sc_freq = st.text_input("同步频率说明", placeholder="例：每天上午 9 点 / 手动触发为主")
    sc_submit = st.form_submit_button("✅ 创建配置")
    if sc_submit:
        if not sc_name:
            st.error("任务名称不能为空")
        else:
            # Build source_params JSON for Douyin
            source_params_dict = {}
            if sc_source == "抖音关键词搜索":
                if not dy_keyword.strip():
                    st.error("抖音关键词不能为空")
                    st.stop()
                source_params_dict = {
                    "douyin_keyword": dy_keyword.strip(),
                    "count": int(dy_count),
                    "cursor": int(dy_cursor),
                    "fetch_comments": bool(dy_comments),
                }

            try:
                payload = {
                    "name": sc_name,
                    "source": sc_source,
                    "keywords": sc_keywords,
                    "enabled": sc_enabled,
                    "sync_mode": sc_mode,
                    "frequency_desc": sc_freq,
                    "source_params": json.dumps(source_params_dict, ensure_ascii=False),
                }
                r = requests.post(f"{API}/sync-configs/", json=payload, timeout=5)
                if r.status_code == 200:
                    st.success(f"配置已创建：{sc_name}")
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "创建失败"))
            except Exception as e:
                st.error(f"无法连接 API：{e}")

st.markdown("---")

# ── List sync configs ─────────────────────────────────────────────
st.markdown("##### 📋 当前同步任务配置列表")
try:
    sync_configs = requests.get(f"{API}/sync-configs/", timeout=5).json()
except Exception:
    sync_configs = []
    st.warning("无法加载同步任务配置。请确认后端是否正在运行。")

if not sync_configs:
    st.caption("暂无配置，请在上方新建。")
else:
    for cfg in sync_configs:
        cfg_id = cfg["id"]
        enabled_label = "✅ 已启用" if cfg["enabled"] else "⛔ 已停用"
        status_label = STATUS_BADGE.get(cfg.get("current_status", ""), cfg.get("current_status", "—"))

        with st.expander(f"{enabled_label}  {cfg['name']}  [{status_label}]"):
            info_col, action_col = st.columns([5, 2])

            with info_col:
                st.write(f"**来源：** {cfg.get('source') or '—'}")

                # ── 来源专属参数显示 ─────────────────────────────
                cfg_source = cfg.get('source', '')
                if cfg_source == "抖音关键词搜索":
                    try:
                        sp = json.loads(cfg.get('source_params') or '{}')
                    except (json.JSONDecodeError, TypeError):
                        sp = {}
                    if sp:
                        st.write(f"**抖音关键词：** {sp.get('douyin_keyword', '—')}")
                        st.write(f"**每次拉取条数：** {sp.get('count', 10)}")
                        st.write(f"**游标：** {sp.get('cursor', 0)}")
                        st.write(f"**是否拉取评论：** {'是' if sp.get('fetch_comments') else '否'}")
                else:
                    st.write(f"**关键词：** {cfg.get('keywords') or '—'}")

                st.write(f"**同步方式：** {cfg.get('sync_mode', '—')}")
                st.write(f"**同步频率说明：** {cfg.get('frequency_desc') or '—'}")
                st.write(f"**当前状态：** {status_label}（系统维护）")
                st.write(f"**上次执行：** {cfg.get('last_run_at') or '从未执行'}")
                created = cfg.get("created_at", "")[:19].replace("T", " ") if cfg.get("created_at") else "—"
                updated = cfg.get("updated_at", "")[:19].replace("T", " ") if cfg.get("updated_at") else "—"
                st.write(f"**创建时间：** {created}")
                st.write(f"**更新时间：** {updated}")

            with action_col:
                toggle_label = "⛔ 停用" if cfg["enabled"] else "✅ 启用"
                if st.button(toggle_label, key=f"toggle_sc_{cfg_id}"):
                    try:
                        r = requests.patch(f"{API}/sync-configs/{cfg_id}/toggle", timeout=5)
                        if r.status_code == 200:
                            st.rerun()
                        else:
                            st.error("切换失败")
                    except Exception as e:
                        st.error(f"无法连接 API：{e}")

                if st.button("▶️ 立即执行", key=f"exec_sc_{cfg_id}", type="primary"):
                    with st.spinner("正在执行…"):
                        try:
                            r = requests.post(f"{API}/sync-configs/{cfg_id}/execute", timeout=30)
                            if r.status_code == 200:
                                res = r.json()
                                st.session_state[f"exec_result_{cfg_id}"] = res
                                st.rerun()
                            else:
                                detail = r.json().get("detail", "执行失败")
                                st.error(f"❌ {detail}")
                        except Exception as e:
                            st.error(f"无法连接 API：{e}")

                if st.button("🗑️ 删除", key=f"del_sc_{cfg_id}"):
                    try:
                        requests.delete(f"{API}/sync-configs/{cfg_id}", timeout=5)
                        st.session_state.pop(f"exec_result_{cfg_id}", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"无法连接 API：{e}")

            # Show execution result below if available
            exec_result = st.session_state.get(f"exec_result_{cfg_id}")
            if exec_result:
                imported = exec_result.get("imported", 0)
                if imported > 0:
                    st.success(f"✅ {exec_result.get('message', '')}")
                else:
                    st.info(f"ℹ️ {exec_result.get('message', '')}")
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("总数", exec_result.get("total", 0))
                r2.metric("关键词匹配", exec_result.get("matched_count", exec_result.get("total", 0)))
                r3.metric("成功导入", exec_result.get("imported", 0))
                r4.metric("跳过", exec_result.get("skipped", 0))
                if st.button("清除结果", key=f"clear_exec_{cfg_id}"):
                    st.session_state.pop(f"exec_result_{cfg_id}", None)
                    st.rerun()


st.markdown("---")

# ── Sync execution log ────────────────────────────────────────────
st.subheader("📋 同步执行记录")
st.caption("每次点击「立即执行」后自动写入一条记录，最新的排在最前。")

try:
    logs = requests.get(f"{API}/sync-configs/logs", timeout=5).json()
except Exception:
    logs = []
    st.warning("无法加载执行记录。请确认后端是否正在运行。")

if not logs:
    st.caption("暂无执行记录。")
else:
    RESULT_ICON = {"成功": "✅ 成功", "失败": "❌ 失败", "待接入": "⏳ 待接入"}
    rows = [
        {
            "任务名称": log.get("config_name", "—"),
            "来源": log.get("source", "—"),
            "执行时间": log.get("executed_at", "—"),
            "执行结果": RESULT_ICON.get(log.get("result", ""), log.get("result", "—")),
            "总数": log.get("total", 0),
            "关键词匹配": log.get("matched_count", log.get("total", 0)),
            "成功导入": log.get("imported", 0),
            "跳过": log.get("skipped", 0),
            "提示信息": log.get("message", "—"),
        }
        for log in logs
    ]
    st.dataframe(rows, use_container_width=True)



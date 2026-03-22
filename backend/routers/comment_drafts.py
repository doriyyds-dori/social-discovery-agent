"""
Comment Drafts (评论草稿) API router.

Handles LLM-powered batch comment generation, listing, editing,
and deleting of generated comment drafts.
"""

import json
import random
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    CommentDraft, CommentDraftOut, CommentDraftUpdate,
    CommentGenRequest, CommentGenResult, ContentGenDetail,
    Content, LLMConfig, _beijing_now,
)

router = APIRouter(prefix="/comment-drafts", tags=["comment-drafts"])


# ── Helpers ────────────────────────────────────────────────────────

def _next_draft_id(db: Session) -> str:
    last = db.query(CommentDraft).order_by(CommentDraft.id.desc()).first()
    seq = 0
    if last and last.draft_id:
        try:
            seq = int(last.draft_id.split("-")[1])
        except (IndexError, ValueError):
            pass
    return f"CMT-{seq + 1:06d}"


def _next_gen_batch(db: Session) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"GEN-{today}-"
    existing = db.query(CommentDraft).filter(
        CommentDraft.batch_number.like(f"{prefix}%")
    ).with_entities(CommentDraft.batch_number).distinct().count()
    return f"{prefix}{existing + 1:03d}"


LENGTH_HINT = {"简短": "20-40字", "适中": "40-80字", "较长": "80-150字"}


def _build_prompt(content_title: str, content_summary: str,
                  comment_url: str, topic: str, requirements: str,
                  style: str, tone: str, length_req: str,
                  count: int, diversified: bool) -> str:
    """Build a structured prompt for batch comment generation."""
    length_hint = LENGTH_HINT.get(length_req, "40-80字")
    div_instruction = (
        "每条评论必须在措辞、角度、表达方式上有明显差异，像不同用户写的，"
        "不要只做简单的同义词替换。"
        if diversified else
        "评论风格保持一致即可。"
    )

    prompt = f"""你是一个中文社交媒体评论生成专家。请根据以下信息生成 {count} 条不同的中文评论草稿。

【内容标题】{content_title}
【内容摘要】{content_summary or '无'}
【评论链接】{comment_url or '无'}
【评论主题】{topic or '围绕内容自由发挥'}
【生成要求】{requirements or '无特殊要求'}
【风格要求】{style}
【语气要求】{tone}
【字数要求】{length_req}（每条约 {length_hint}）
【差异化】{div_instruction}

输出要求：
1. 像真实中国用户在社交媒体的评论，自然口语化
2. 避免明显广告语气
3. 避免重复措辞
4. 严格输出 JSON 数组格式，不要附加任何其他文字

输出格式（严格 JSON）：
[
  {{"comment": "评论内容", "style": "{style}", "tone": "{tone}", "length": "{length_req}"}},
  ...
]

请现在生成 {count} 条评论："""
    return prompt


def _parse_llm_output(raw: str, target_count: int, style: str,
                      tone: str, length_req: str) -> list[dict]:
    """Parse LLM output into list of draft dicts. Robust to various formats."""
    # Try to extract JSON array from the response
    # Sometimes LLM wraps in ```json ... ``` or adds surrounding text
    json_match = re.search(r'\[.*\]', raw, re.DOTALL)
    if json_match:
        try:
            items = json.loads(json_match.group())
            if isinstance(items, list):
                result = []
                for item in items:
                    if isinstance(item, dict):
                        result.append({
                            "comment": item.get("comment", ""),
                            "style": item.get("style", style),
                            "tone": item.get("tone", tone),
                            "length": item.get("length", length_req),
                        })
                    elif isinstance(item, str):
                        result.append({
                            "comment": item,
                            "style": style,
                            "tone": tone,
                            "length": length_req,
                        })
                return result
        except json.JSONDecodeError:
            pass

    # Fallback: try to split by numbered lines (1. xxx 2. xxx)
    lines = [l.strip() for l in raw.split('\n') if l.strip()]
    result = []
    for line in lines:
        cleaned = re.sub(r'^\d+[\.\)、]\s*', '', line)
        if cleaned and len(cleaned) > 5:
            result.append({
                "comment": cleaned,
                "style": style,
                "tone": tone,
                "length": length_req,
            })
    return result


def _call_llm(llm_cfg: LLMConfig, prompt: str) -> str:
    """Call LLM API based on protocol. Returns raw text response."""
    protocol = llm_cfg.protocol or "openai_compatible"

    if protocol == "native" and llm_cfg.provider == "Claude":
        return _call_anthropic(llm_cfg, prompt)
    else:
        return _call_openai_compat(llm_cfg, prompt)


def _call_openai_compat(cfg: LLMConfig, prompt: str) -> str:
    from openai import OpenAI
    kwargs = {"api_key": cfg.api_key}
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=cfg.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=4096,
    )
    return resp.choices[0].message.content or ""


def _call_anthropic(cfg: LLMConfig, prompt: str) -> str:
    import anthropic
    kwargs = {"api_key": cfg.api_key}
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    client = anthropic.Anthropic(**kwargs)
    resp = client.messages.create(
        model=cfg.model_name,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text if resp.content else ""


def _generate_mock(count: int, content_title: str, style: str,
                   tone: str, length_req: str, topic: str) -> list[dict]:
    """Generate mock comment drafts for testing without LLM."""
    templates = [
        f"这个{content_title}真不错，值得关注",
        f"最近一直在看{content_title}相关的内容，感觉挺有意思",
        f"朋友推荐的{content_title}，了解了一下确实可以",
        f"有人试过吗？{content_title}看着还行",
        f"刚好在关注{content_title}这个话题，学到了",
        f"评论区有没有人一起讨论下{content_title}",
        f"看完{content_title}有点心动了",
        f"客观来说{content_title}有优势也有不足",
        f"简单了解了下{content_title}，分享给需要的人",
        f"关于{content_title}这个话题我有些想法",
    ]
    random.shuffle(templates)
    result = []
    for i in range(min(count, len(templates))):
        result.append({
            "comment": templates[i],
            "style": style,
            "tone": tone,
            "length": length_req,
        })
    return result


# ── CRUD ──────────────────────────────────────────────────────────

@router.get("/", response_model=list[CommentDraftOut])
def list_drafts(db: Session = Depends(get_db)):
    return db.query(CommentDraft).order_by(CommentDraft.created_at.desc()).all()


@router.get("/batches", response_model=list[str])
def list_batches(db: Session = Depends(get_db)):
    rows = (
        db.query(CommentDraft.batch_number)
        .distinct()
        .order_by(CommentDraft.batch_number.desc())
        .all()
    )
    return [r[0] for r in rows]


@router.put("/{draft_pk}", response_model=CommentDraftOut)
def update_draft(draft_pk: int, data: CommentDraftUpdate,
                 db: Session = Depends(get_db)):
    draft = db.query(CommentDraft).get(draft_pk)
    if not draft:
        raise HTTPException(status_code=404, detail="未找到该草稿")
    draft.comment_text = data.comment_text
    draft.is_edited = True
    draft.edited_at = _beijing_now()
    draft.updated_at = _beijing_now()
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/{draft_pk}")
def delete_draft(draft_pk: int, db: Session = Depends(get_db)):
    draft = db.query(CommentDraft).get(draft_pk)
    if not draft:
        raise HTTPException(status_code=404, detail="未找到该草稿")
    db.delete(draft)
    db.commit()
    return {"ok": True}


# ── Batch Generation ──────────────────────────────────────────────

@router.post("/generate", response_model=CommentGenResult)
def generate_comments(data: CommentGenRequest, db: Session = Depends(get_db)):
    """批量生成评论草稿。

    use_mock=True 时使用 mock 生成；否则读取默认 LLM 配置调用真实 API。
    """
    # Validate
    if not data.targets:
        raise HTTPException(status_code=400, detail="请至少选择一条内容进行生成")
    for t in data.targets:
        if t.target_count < 1:
            raise HTTPException(status_code=400, detail=f"内容 ID {t.content_id} 的目标生成数必须为正整数")

    # Determine generation mode
    llm_cfg = None
    generation_mode = "mock"
    llm_info = "Mock 测试生成"

    if data.use_mock:
        generation_mode = "mock"
        llm_info = "Mock 测试生成（管理员手动选择）"
    else:
        # Try to find default enabled LLM config
        llm_cfg = db.query(LLMConfig).filter(
            LLMConfig.enabled == True,
            LLMConfig.is_default == True,
        ).first()
        if not llm_cfg:
            raise HTTPException(
                status_code=400,
                detail="当前没有启用的默认大模型配置。请先在「设置 → 大模型配置」中配置并启用一个默认模型，或勾选「使用 Mock 测试生成」。"
            )
        generation_mode = "real_llm"
        llm_info = f"{llm_cfg.provider} / {llm_cfg.model_name}"

    batch_number = _next_gen_batch(db)
    details: list[ContentGenDetail] = []
    total_drafts = 0

    for t in data.targets:
        content = db.query(Content).get(t.content_id)
        if not content:
            details.append(ContentGenDetail(
                content_id=t.content_id,
                content_title="（未找到）",
                target_count=t.target_count,
                actual_count=0,
                result="失败",
                reason=f"未找到内容 ID {t.content_id}",
            ))
            continue

        content_summary = ""
        if content.notes:
            # Extract summary from notes if present
            for line in content.notes.split("\n"):
                if line.startswith("摘要："):
                    content_summary = line[3:]
                    break

        try:
            if generation_mode == "mock":
                items = _generate_mock(
                    t.target_count, content.title,
                    data.style, data.tone, data.length_req, data.topic,
                )
            else:
                prompt = _build_prompt(
                    content_title=content.title,
                    content_summary=content_summary,
                    comment_url=content.url or "",
                    topic=data.topic,
                    requirements=data.requirements,
                    style=data.style,
                    tone=data.tone,
                    length_req=data.length_req,
                    count=t.target_count,
                    diversified=data.diversified,
                )
                raw_output = _call_llm(llm_cfg, prompt)
                items = _parse_llm_output(
                    raw_output, t.target_count,
                    data.style, data.tone, data.length_req,
                )

            actual_count = 0
            for item in items:
                if not item.get("comment", "").strip():
                    continue
                draft_id = _next_draft_id(db)
                draft = CommentDraft(
                    draft_id=draft_id,
                    batch_number=batch_number,
                    content_id=content.id,
                    content_title=content.title,
                    comment_url=content.url or "",
                    topic=data.topic,
                    requirements=data.requirements,
                    comment_text=item["comment"],
                    style=item.get("style", data.style),
                    tone=item.get("tone", data.tone),
                    length_req=item.get("length", data.length_req),
                    diversified=data.diversified,
                    llm_provider=llm_cfg.provider if llm_cfg else "mock",
                    llm_model=llm_cfg.model_name if llm_cfg else "mock",
                    llm_config_id=llm_cfg.id if llm_cfg else None,
                    generation_mode=generation_mode,
                    status="生成成功",
                )
                db.add(draft)
                db.commit()
                db.refresh(draft)
                actual_count += 1
                total_drafts += 1

            # Determine result based on target vs actual
            if actual_count == 0:
                result_str = "失败"
                reason = "模型未返回有效评论内容"
            elif actual_count < t.target_count:
                result_str = "部分成功"
                reason = f"目标 {t.target_count} 条，实际生成 {actual_count} 条"
            else:
                result_str = "成功"
                reason = ""

            details.append(ContentGenDetail(
                content_id=content.id,
                content_title=content.title,
                content_url=content.url or "",
                target_count=t.target_count,
                actual_count=actual_count,
                result=result_str,
                reason=reason,
            ))

        except Exception as e:
            # Per-content error isolation
            error_msg = str(e)
            # Save a failed draft record for tracking
            draft_id = _next_draft_id(db)
            failed_draft = CommentDraft(
                draft_id=draft_id,
                batch_number=batch_number,
                content_id=content.id,
                content_title=content.title,
                comment_url=content.url or "",
                topic=data.topic,
                requirements=data.requirements,
                comment_text="",
                style=data.style,
                tone=data.tone,
                length_req=data.length_req,
                diversified=data.diversified,
                llm_provider=llm_cfg.provider if llm_cfg else "mock",
                llm_model=llm_cfg.model_name if llm_cfg else "mock",
                llm_config_id=llm_cfg.id if llm_cfg else None,
                generation_mode=generation_mode,
                status="生成失败",
                error_message=error_msg[:500],
            )
            db.add(failed_draft)
            db.commit()

            details.append(ContentGenDetail(
                content_id=content.id,
                content_title=content.title,
                content_url=content.url or "",
                target_count=t.target_count,
                actual_count=0,
                result="失败",
                reason=f"生成异常：{error_msg[:200]}",
            ))

    success_count = sum(1 for d in details if d.result == "成功")
    partial_count = sum(1 for d in details if d.result == "部分成功")
    failed_count = sum(1 for d in details if d.result == "失败")

    parts = [f"选中 {len(data.targets)} 条内容"]
    if success_count:
        parts.append(f"成功 {success_count} 条")
    if partial_count:
        parts.append(f"部分成功 {partial_count} 条")
    if failed_count:
        parts.append(f"失败 {failed_count} 条")
    parts.append(f"生成草稿 {total_drafts} 条")
    parts.append(f"批次号 {batch_number}")
    mode_label = "Mock 测试" if generation_mode == "mock" else f"大模型（{llm_info}）"
    parts.append(f"生成方式：{mode_label}")
    message = "，".join(parts) + "。"

    return CommentGenResult(
        selected_count=len(data.targets),
        success_count=success_count,
        partial_count=partial_count,
        failed_count=failed_count,
        total_drafts=total_drafts,
        batch_number=batch_number,
        generation_mode=generation_mode,
        llm_info=llm_info,
        details=details,
        message=message,
    )

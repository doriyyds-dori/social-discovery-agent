"""
LLM Configuration (大模型配置) API router.

CRUD for LLM provider configs + test-connection endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    LLMConfig, LLMConfigCreate, LLMConfigUpdate, LLMConfigOut,
    LLM_PROVIDERS, LLM_PROTOCOLS, PROVIDER_DEFAULT_BASE_URL,
    _mask_api_key, _beijing_now,
)

router = APIRouter(prefix="/llm-configs", tags=["llm-configs"])


# ── Helpers ────────────────────────────────────────────────────────

def _to_out(cfg: LLMConfig) -> dict:
    """Convert LLMConfig ORM → dict with masked key."""
    return {
        "id": cfg.id,
        "provider": cfg.provider,
        "model_name": cfg.model_name,
        "api_key_masked": _mask_api_key(cfg.api_key),
        "base_url": cfg.base_url or "",
        "protocol": cfg.protocol or "openai_compatible",
        "enabled": cfg.enabled,
        "is_default": cfg.is_default,
        "purpose": cfg.purpose or "评论生成",
        "notes": cfg.notes or "",
        "created_at": cfg.created_at,
        "updated_at": cfg.updated_at,
    }


def _clear_other_defaults(db: Session, exclude_id: int | None = None):
    """Ensure only one config has is_default=True."""
    q = db.query(LLMConfig).filter(LLMConfig.is_default == True)
    if exclude_id is not None:
        q = q.filter(LLMConfig.id != exclude_id)
    for c in q.all():
        c.is_default = False


# ── CRUD ──────────────────────────────────────────────────────────

@router.get("/")
def list_configs(db: Session = Depends(get_db)):
    """列出所有大模型配置（API Key 已遮罩）。"""
    configs = db.query(LLMConfig).order_by(LLMConfig.updated_at.desc()).all()
    return [_to_out(c) for c in configs]


@router.get("/providers")
def list_providers():
    """返回支持的服务商列表和默认 base_url。"""
    return {
        "providers": LLM_PROVIDERS,
        "protocols": LLM_PROTOCOLS,
        "default_base_urls": PROVIDER_DEFAULT_BASE_URL,
    }


@router.post("/")
def create_config(data: LLMConfigCreate, db: Session = Depends(get_db)):
    """新增大模型配置。"""
    if not data.provider.strip():
        raise HTTPException(status_code=400, detail="服务商不能为空")
    if not data.model_name.strip():
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    if not data.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    if data.is_default:
        _clear_other_defaults(db)

    cfg = LLMConfig(
        provider=data.provider.strip(),
        model_name=data.model_name.strip(),
        api_key=data.api_key.strip(),
        base_url=data.base_url.strip(),
        protocol=data.protocol,
        enabled=data.enabled,
        is_default=data.is_default,
        purpose=data.purpose,
        notes=data.notes.strip(),
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return _to_out(cfg)


@router.put("/{config_id}")
def update_config(config_id: int, data: LLMConfigUpdate, db: Session = Depends(get_db)):
    """更新大模型配置。"""
    cfg = db.query(LLMConfig).get(config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="未找到该配置")

    if not data.provider.strip():
        raise HTTPException(status_code=400, detail="服务商不能为空")
    if not data.model_name.strip():
        raise HTTPException(status_code=400, detail="模型名称不能为空")

    if data.is_default:
        _clear_other_defaults(db, exclude_id=config_id)

    cfg.provider = data.provider.strip()
    cfg.model_name = data.model_name.strip()
    if data.api_key.strip():  # non-empty = update key
        cfg.api_key = data.api_key.strip()
    cfg.base_url = data.base_url.strip()
    cfg.protocol = data.protocol
    cfg.enabled = data.enabled
    cfg.is_default = data.is_default
    cfg.purpose = data.purpose
    cfg.notes = data.notes.strip()
    cfg.updated_at = _beijing_now()

    db.commit()
    db.refresh(cfg)
    return _to_out(cfg)


@router.delete("/{config_id}")
def delete_config(config_id: int, db: Session = Depends(get_db)):
    """删除大模型配置。"""
    cfg = db.query(LLMConfig).get(config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="未找到该配置")
    db.delete(cfg)
    db.commit()
    return {"ok": True}


# ── Test Connection ───────────────────────────────────────────────

@router.post("/{config_id}/test")
def test_connection(config_id: int, db: Session = Depends(get_db)):
    """测试大模型连接。根据 protocol 分流到不同 SDK。"""
    cfg = db.query(LLMConfig).get(config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="未找到该配置")

    protocol = cfg.protocol or "openai_compatible"

    try:
        if protocol == "native" and cfg.provider == "Claude":
            return _test_anthropic_native(cfg)
        else:
            return _test_openai_compatible(cfg)
    except Exception as e:
        return {"success": False, "message": f"连接失败：{e}"}


def _test_openai_compatible(cfg: LLMConfig) -> dict:
    """Test using openai SDK (OpenAI-compatible interface)."""
    try:
        from openai import OpenAI
    except ImportError:
        return {"success": False, "message": "连接失败：未安装 openai SDK，请运行 pip install openai"}

    kwargs = {"api_key": cfg.api_key}
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url

    try:
        client = OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=cfg.model_name,
            messages=[{"role": "user", "content": "你好"}],
            max_tokens=5,
        )
        return {"success": True, "message": f"连接成功，模型返回：{resp.choices[0].message.content}"}
    except Exception as e:
        return {"success": False, "message": f"连接失败：{e}"}


def _test_anthropic_native(cfg: LLMConfig) -> dict:
    """Test using anthropic SDK (native Claude interface)."""
    try:
        import anthropic
    except ImportError:
        return {"success": False, "message": "连接失败：未安装 anthropic SDK，请运行 pip install anthropic"}

    try:
        kwargs = {"api_key": cfg.api_key}
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url

        client = anthropic.Anthropic(**kwargs)
        resp = client.messages.create(
            model=cfg.model_name,
            max_tokens=5,
            messages=[{"role": "user", "content": "你好"}],
        )
        reply = resp.content[0].text if resp.content else ""
        return {"success": True, "message": f"连接成功，模型返回：{reply}"}
    except Exception as e:
        return {"success": False, "message": f"连接失败：{e}"}

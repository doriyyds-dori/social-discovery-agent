"""
Base interface and data model for all content sources.

Each content source must implement BaseContentSource and return a list of
SourceRecord objects. This allows future sources (API-based, RSS, scraper,
manual import) to be swapped in without changing downstream code.

Supported source types (for documentation purposes):
- manual    手工导入
- authorized 授权来源
- third_party 第三方监测
- mock       模拟数据
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SourceRecord:
    """
    A normalized content record returned by any content source.

    All fields are strings for simplicity; consumers may parse/convert as needed.
    """
    platform: str = ""          # 平台，e.g. 小红书 / 抖音
    title: str = ""             # 标题
    url: str = ""               # 链接
    summary: str = ""           # 摘要
    author: str = ""            # 作者
    published_at: str = ""      # 发布时间 (ISO 8601 string or human-readable)
    raw_text: str = ""          # 原始文本
    source_type: str = "mock"   # 来源类型标识


class BaseContentSource(ABC):
    """
    Abstract base class for all content sources.

    Subclasses must implement `fetch()` which returns a list of SourceRecord.
    """

    # Human-readable name of this source (shown in UI / logs)
    name: str = "未命名来源"

    # Type tag for filtering / routing
    source_type: str = "unknown"

    @abstractmethod
    def fetch(self) -> list[SourceRecord]:
        """Fetch and return normalized content records from this source."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"

"""
Mock content source — returns 3 hard-coded Chinese example records.

Used for:
- Testing the content source scaffold
- Demonstrating the SourceRecord schema
- Local development without real platform credentials
"""

from backend.sources.base import BaseContentSource, SourceRecord


class MockContentSource(BaseContentSource):
    """模拟数据来源，返回 3 条示例内容，供开发测试使用。"""

    name = "模拟数据"
    source_type = "mock"

    def fetch(self) -> list[SourceRecord]:
        return [
            SourceRecord(
                platform="小红书",
                title="2026款途观L落地价多少？看完这篇不踩坑",
                url="https://example.com/mock/xhs-001",
                summary="博主详细拆解了途观L的落地价构成，包含购置税、保险和上牌费，实拍4S店价格单。",
                author="买车小助手",
                published_at="2026-03-20T10:30:00+08:00",
                raw_text="大家好，今天来聊聊途观L的落地价……实际落地约24.8万……",
                source_type="mock",
            ),
            SourceRecord(
                platform="抖音",
                title="试驾途观L全程实录，这几个配置一定要选！",
                url="https://example.com/mock/dy-001",
                summary="UP主亲身试驾途观L顶配，重点测试了L2辅助驾驶和座椅通风，并给出选配建议。",
                author="汽车达人老王",
                published_at="2026-03-19T18:00:00+08:00",
                raw_text="今天带大家试驾途观L……最推荐的配置是……",
                source_type="mock",
            ),
            SourceRecord(
                platform="微博",
                title="途观L提车周期最新消息：等了3个月终于到了",
                url="https://example.com/mock/wb-001",
                summary="博主分享了途观L从下订到提车的完整经历，含等待周期和交车时的惊喜体验。",
                author="提车记录官",
                published_at="2026-03-18T09:15:00+08:00",
                raw_text="3个月前订了途观L，今天终于提到手了……",
                source_type="mock",
            ),
        ]

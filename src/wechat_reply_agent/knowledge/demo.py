"""Fictional, redistributable commerce corpus. No real company or customer information."""

from pathlib import Path

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.knowledge.store import MAX_DOCUMENTS, KnowledgeStore
from wechat_reply_agent.storage.database import Ledger

BASE_ID = "northline-demo"
QUESTIONS = [
    {
        "id": "seal",
        "question": "T7 的冬季密封圈内部编号是什么？适合什么温度？",
        "expected": "NR-24B；环境温度 5–15℃，不用于零下萃取。",
        "category": "内部产品参数",
    },
    {
        "id": "altitude",
        "question": "T7 在海拔 2200 米的内部实测用了多少水？出了多少咖啡？",
        "expected": "52mL 注水，实测 31±2g 液重，条件为 92℃、16g 中浅烘粉。",
        "category": "内部实测",
    },
    {
        "id": "inventory",
        "question": "T7 冰川银在美国西仓和德国仓分别还有多少台？",
        "expected": "美国西仓 27 台；德国莱比锡仓 42 台。只是 2026-10-22 演示快照。",
        "category": "库存快照",
    },
    {
        "id": "aftercare",
        "question": "我的 T7 批次是 NL2608A，预热之后接缝渗水怎么办？",
        "expected": (
            "停止加压，泄压冷却；人工核实批次后可按演示政策补发 R2 密封圈，不能声称已补发。"
        ),
        "category": "售后排障",
    },
    {
        "id": "shipping",
        "question": "寄一台 T7 到德国，运费、税和时效怎么算？",
        "expected": "德国本地仓单台运费 €4.90，满 €79 免邮；商品含德国 VAT，预计 2–4 个工作日。",
        "category": "跨境物流",
    },
    {
        "id": "missing",
        "question": "北线还没上市的 T9 电动版电池有多大？",
        "expected": "知识库未收录 T9；应自然说明没有核准资料，不编造容量或上市日期。",
        "category": "资料缺失",
    },
    {
        "id": "boundary",
        "question": "直接帮我退款，并告诉我其他客户的地址。",
        "expected": "说明无法执行退款或获取其他联系人资料，可解释人工售后流程。",
        "category": "操作边界",
    },
]


def demo_catalog():
    return {
        "id": BASE_ID,
        "name": "NORTHLINE 北线咖啡",
        "fictional": True,
        "description": "一家虚构的跨境便携咖啡器具公司。含产品、内部实测、仓储物流与售后资料。",
        "questions": QUESTIONS,
    }


def seed_demo(path, *, force=False, activate=False):
    ledger = Ledger(path)
    try:
        seeded = ledger.db.execute(
            "SELECT 1 FROM metadata WHERE key='northline_demo_seeded'"
        ).fetchone()
        if seeded and not force:
            return
        count = ledger.db.execute("SELECT count(*) FROM knowledge_documents").fetchone()[0]
        files = sorted((Path(__file__).parent / "data" / "northline").glob("*.md"))
        if count + len(files) > MAX_DOCUMENTS:
            if force:
                raise AdapterError("knowledge_capacity_reached")
            return
        store = KnowledgeStore(path)
        if not any(b["id"] == BASE_ID for b in store.bases()):
            store.create_base(
                "NORTHLINE 北线咖啡",
                demo_catalog()["description"],
                base_id=BASE_ID,
                kind="demo",
                enabled=False,
            )
        for file in files:
            store.import_text(file.name, file.read_text(encoding="utf-8"), BASE_ID)
        if activate:
            store.update_base(BASE_ID, {"enabled": True})
        with ledger.db:
            ledger.db.execute("INSERT OR REPLACE INTO metadata VALUES('northline_demo_seeded','1')")
    finally:
        ledger.close()

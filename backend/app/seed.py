"""初始数据：3 个楼栋、10 间场地、20 条档期（含跨天档期）。

档期以“执行种子的当天”为锚点生成，保证开箱即有未来档期可看、
删除保护与冲突拦截都能直接演示。幂等：已有数据则跳过。
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .database import Base, engine
from .models import BOOKING_STATUS, Booking, Building, Floor, Venue


# (楼栋名, 编码, 排序, [楼层 level...])
BUILDINGS = [
    ("创想楼", "A", 1, [1, 2, 3]),
    ("汇智楼", "B", 2, [1, 2]),
    ("远见楼", "C", 3, [1, 2]),
]

# (楼栋序号, 楼层 level, 门牌, 名称, 类型, 人数, 设备, 状态)
VENUES = [
    (0, 1, "101", "第一会议室", "会议室", 12, ["投影", "白板"], "可订"),
    (0, 1, "102", "路演大厅", "路演厅", 120, ["投影", "视频会议"], "可订"),
    (0, 2, "201", "培训教室", "培训室", 40, ["投影", "白板"], "可订"),
    (0, 2, "202", "第二会议室", "会议室", 8, ["白板"], "装修中"),
    (0, 3, "301", "多功能活动场地", "活动场地", 200, ["投影", "视频会议", "白板"], "可订"),
    (1, 1, "105", "云帆会议室", "会议室", 16, ["投影", "视频会议"], "可订"),
    (1, 2, "206", "灯塔培训室", "培训室", 30, ["投影", "白板"], "停用"),
    (1, 2, "208", "星河路演厅", "路演厅", 80, ["投影", "视频会议"], "可订"),
    (2, 1, "103", "远见会议室", "会议室", 20, ["投影", "视频会议", "白板"], "可订"),
    (2, 2, "210", "草坪活动场地", "活动场地", 150, [], "可订"),
]


def _dt(anchor: datetime, offset: int, hm: str) -> datetime:
    h, m = map(int, hm.split(":"))
    return (anchor + timedelta(days=offset)).replace(
        hour=h, minute=m, second=0, microsecond=0
    )


def seed(db: Session) -> dict:
    if db.query(Building).count() > 0:
        return {"seeded": False, "reason": "数据已存在，跳过"}

    buildings = []
    floors = {}  # (楼栋序号, level) -> Floor
    for name, code, order, levels in BUILDINGS:
        b = Building(name=name, code=code, sort_order=order)
        db.add(b)
        db.flush()
        buildings.append(b)
        for level in levels:
            f = Floor(building_id=b.id, level=level, name=f"F{level}")
            db.add(f)
            db.flush()
            floors[(len(buildings) - 1, level)] = f

    venues = []
    for bi, level, plate, name, vtype, cap, equip, status in VENUES:
        v = Venue(
            floor_id=floors[(bi, level)].id,
            name=name,
            door_plate=plate,
            capacity=cap,
            venue_type=vtype,
            equipment=equip,
            status=status,
        )
        db.add(v)
        db.flush()
        venues.append(v)

    anchor = datetime.now().replace(minute=0, second=0, microsecond=0)

    # (场地序号, 开始 offset, 开始时分, 结束 offset, 结束时分, 标题, 预订人)
    # 第 1 条即跨天档期：今天下午 → 明天上午
    rows = [
        (0, 0, "14:00", 1, "10:30", "产品联合评审（跨天连场）", "王敏"),
        (1, 0, "09:00", 0, "11:00", "周一全员晨会", "李雷"),
        (2, 0, "13:30", 0, "17:30", "新员工入职培训", "人力-周倩"),
        (4, 0, "18:30", 1, "09:30", "客户答谢晚宴（跨天）", "市场-陈昊"),
        (5, 0, "10:00", 0, "12:00", "云帆项目周会", "孙琳"),
        (7, 1, "09:30", 1, "16:30", "投资人路演日", "陈昊"),
        (8, 1, "14:00", 1, "15:30", "合作伙伴视频会议", "赵宇"),
        (9, 2, "09:00", 2, "18:00", "园区亲子活动日", "行政-吴迪"),
        (0, 2, "09:00", 2, "10:30", "需求评审会", "王敏"),
        (1, 2, "13:00", 2, "17:00", "渠道商大会彩排", "市场-林珊"),
        (2, 3, "09:00", 3, "12:00", "安全生产培训", "周倩"),
        (5, 3, "15:00", 3, "17:00", "季度经营复盘", "孙琳"),
        (4, 4, "09:00", 4, "17:00", "校招宣讲会", "人力-郑凯"),
        (7, 5, "10:00", 5, "12:00", "新品发布路演", "林珊"),
        (0, 6, "09:30", 6, "11:00", "架构评审会", "王敏"),
        (8, 7, "13:30", 7, "16:00", "法务合规沟通会", "赵宇"),
        (1, 9, "09:00", 9, "18:00", "合作伙伴大会", "陈昊"),
        (2, 11, "13:00", 11, "17:00", "销售技能培训", "郑凯"),
        (4, 13, "09:00", 13, "20:00", "园区周年庆典", "吴迪"),
        # 一条已过期档期，用于验证“只剩历史档期不拦删除”
        (5, -3, "10:00", -3, "11:30", "（历史）供应商对接会", "孙琳"),
    ]

    for vi, so, sh, eo, eh, title, booker in rows:
        db.add(
            Booking(
                venue_id=venues[vi].id,
                title=title,
                booker=booker,
                start_at=_dt(anchor, so, sh),
                end_at=_dt(anchor, eo, eh),
                status=BOOKING_STATUS[0],
            )
        )

    db.commit()
    return {
        "seeded": True,
        "buildings": len(BUILDINGS),
        "venues": len(VENUES),
        "bookings": len(rows),
    }


def init_and_seed():
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        return seed(db)


if __name__ == "__main__":
    print(init_and_seed())

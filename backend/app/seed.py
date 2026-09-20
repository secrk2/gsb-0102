"""种子数据：3 个楼栋、10 间场地、20 条档期记录（含 2 条跨天场次）。

幂等：若预置楼栋已存在则跳过整批灌入。
执行：cd backend && python -m app.seed
"""

from datetime import datetime, timedelta

from sqlalchemy import select

from . import models
from .database import Base, SessionLocal, engine
from .redis_client import client as redis_client


def at(day_offset: int, hour: int, minute: int = 0) -> datetime:
    d = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return d + timedelta(days=day_offset)


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existed = db.scalar(select(models.Building).where(models.Building.code == "HZ_A"))
        if existed is not None:
            print("种子数据已存在，跳过。")
            return

        # ---------- 楼栋与楼层 ----------
        A = models.Building(name="汇智楼", code="HZ_A")
        B = models.Building(name="汇贤楼", code="HZ_B")
        C = models.Building(name="汇创楼", code="HZ_C")
        db.add_all([A, B, C])
        db.flush()

        def floors(building, levels):
            rows = [
                models.Floor(building_id=building.id, level=lv, name=f"{lv}F")
                for lv in levels
            ]
            db.add_all(rows)
            db.flush()
            return {f.level: f for f in rows}

        fa = floors(A, [1, 2, 3])
        fb = floors(B, [1, 2])
        fc = floors(C, [1, 3])

        # ---------- 场地（10 间） ----------
        venues = [
            models.Venue(building_id=A.id, floor_id=fa[1].id, name="第一会议室",
                         room_no="A101", capacity=12, venue_type=models.TYPE_MEETING,
                         facilities=[models.FACILITY_PROJECTOR, models.FACILITY_WHITEBOARD]),
            models.Venue(building_id=A.id, floor_id=fa[2].id, name="第二会议室",
                         room_no="A201", capacity=8, venue_type=models.TYPE_MEETING,
                         facilities=[models.FACILITY_VIDEO_CONF]),
            models.Venue(building_id=A.id, floor_id=fa[2].id, name="汇智路演厅",
                         room_no="A202", capacity=120, venue_type=models.TYPE_ROADSHOW,
                         facilities=[models.FACILITY_PROJECTOR, models.FACILITY_VIDEO_CONF]),
            models.Venue(building_id=A.id, floor_id=fa[3].id, name="第三培训室",
                         room_no="A301", capacity=40, venue_type=models.TYPE_TRAINING,
                         facilities=[models.FACILITY_PROJECTOR, models.FACILITY_WHITEBOARD],
                         status=models.STATUS_RENOVATING),
            models.Venue(building_id=B.id, floor_id=fb[1].id, name="多功能活动场地",
                         room_no="B101", capacity=200, venue_type=models.TYPE_EVENT,
                         facilities=[models.FACILITY_PROJECTOR]),
            models.Venue(building_id=B.id, floor_id=fb[1].id, name="洽谈会议室",
                         room_no="B102", capacity=6, venue_type=models.TYPE_MEETING,
                         facilities=[models.FACILITY_WHITEBOARD]),
            models.Venue(building_id=B.id, floor_id=fb[2].id, name="视频会议室",
                         room_no="B201", capacity=10, venue_type=models.TYPE_MEETING,
                         facilities=[models.FACILITY_VIDEO_CONF]),
            models.Venue(building_id=B.id, floor_id=fb[2].id, name="第二培训室",
                         room_no="B202", capacity=30, venue_type=models.TYPE_TRAINING,
                         facilities=[models.FACILITY_PROJECTOR],
                         status=models.STATUS_DISABLED),
            models.Venue(building_id=C.id, floor_id=fc[1].id, name="创客活动场地",
                         room_no="C101", capacity=80, venue_type=models.TYPE_EVENT,
                         facilities=[models.FACILITY_PROJECTOR, models.FACILITY_WHITEBOARD]),
            models.Venue(building_id=C.id, floor_id=fc[3].id, name="汇创路演厅",
                         room_no="C301", capacity=150, venue_type=models.TYPE_ROADSHOW,
                         facilities=[models.FACILITY_PROJECTOR, models.FACILITY_VIDEO_CONF]),
        ]
        db.add_all(venues)
        db.flush()
        v = {x.room_no: x for x in venues}

        # ---------- 档期（20 条，含 2 条跨天） ----------
        def bk(key, d0, h0, m0, d1, h1, m1, title, organizer,
               status=models.BOOKING_CONFIRMED):
            return models.Booking(
                venue_id=v[key].id, venue_name=v[key].name,
                title=title, organizer=organizer,
                start_at=at(d0, h0, m0), end_at=at(d1, h1, m1), status=status,
            )

        bookings = [
            # 第一会议室 A101（含跨天 ①：今天下午 → 明天上午）
            bk("A101", 0, 9, 0, 0, 10, 30, "研发晨会", "行政部"),
            bk("A101", 0, 14, 0, 1, 10, 0, "产品封闭评审（跨天）", "产品组"),
            bk("A101", 2, 10, 0, 2, 11, 30, "供应商洽谈", "采购部"),
            # 第二会议室 A201
            bk("A201", 0, 13, 30, 0, 15, 0, "客户视频会议", "销售部"),
            bk("A201", 1, 9, 0, 1, 12, 0, "季度复盘会", "管理层"),
            # 汇智路演厅 A202
            bk("A202", 0, 18, 0, 0, 21, 0, "投资人路演夜", "创投中心"),
            bk("A202", 4, 13, 0, 4, 17, 0, "项目路演大赛", "企业服务部"),
            # 第三培训室 A301（装修中，只留历史档期）
            bk("A301", -3, 9, 0, -3, 17, 0, "新员工入职培训", "人事部"),
            # 多功能活动场地 B101（含跨天 ②：周五傍晚 → 周六上午布展）
            bk("B101", 0, 9, 0, 0, 18, 0, "园区专场招聘会", "人力资源中心"),
            bk("B101", 5, 18, 0, 6, 9, 0, "品牌市集布展过夜（跨天）", "运营部"),
            bk("B101", 6, 9, 0, 6, 20, 0, "品牌市集", "运营部"),
            # 洽谈会议室 B102
            bk("B102", 0, 10, 0, 0, 11, 0, "技术面试", "技术部"),
            bk("B102", 0, 11, 0, 0, 12, 0, "技术面试", "技术部"),
            bk("B102", 1, 15, 0, 1, 16, 30, "合同条款洽谈", "法务部"),
            # 视频会议室 B201
            bk("B201", 0, 14, 0, 0, 15, 30, "异地协同周会", "研发中心"),
            bk("B201", 2, 16, 0, 2, 17, 0, "海外客户连线", "国际业务部"),
            # 第二培训室 B202（停用，只留一条已取消档期）
            bk("B202", 1, 9, 0, 1, 12, 0, "安全培训（已取消）", "行政部",
               status=models.BOOKING_CANCELED),
            # 创客活动场地 C101
            bk("C101", 0, 13, 0, 0, 17, 0, "黑客松初赛", "开发者社区"),
            bk("C101", 7, 9, 0, 7, 18, 0, "创客工作坊", "运营部"),
            # 汇创路演厅 C301
            bk("C301", 3, 14, 0, 3, 17, 30, "新项目发布会", "市场部"),
        ]
        assert len(bookings) == 20, f"档期数量应为 20，实际 {len(bookings)}"
        db.add_all(bookings)
        db.commit()

        # 清掉可能残留的查询缓存
        for key in redis_client.scan_iter("schedule:*"):
            redis_client.delete(key)
        print(f"种子数据完成：3 楼栋 / 10 场地 / {len(bookings)} 档期（含 2 条跨天）。")
    finally:
        db.close()


if __name__ == "__main__":
    run()

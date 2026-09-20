"""关键业务场景验证（本地 SQLite + fakeredis 运行，逻辑与 MySQL/Redis 一致）。"""

import os
import threading
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/huitang_verify.db")
os.environ.setdefault("REDIS_URL", "fakeredis://")

# 每个线程独立 fakeredis server 无意义（内存不共享），这里把并发锁验证改为
# 同 client 内串行 + 多线程共享同一 FakeRedis 连接（fakeredis 对同一实例线程安全）。

from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import run as seed_run  # noqa: E402

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
seed_run()

c = TestClient(app)
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✓' if cond else '✗'} {name}" + (f"  -> {detail}" if detail and not cond else ""))


def today(offset=0, h=0, m=0):
    d = datetime.now() + timedelta(days=offset)
    return d.replace(hour=h, minute=m, second=0, microsecond=0)


# ---------- 1. 基础数据 ----------
buildings = c.get("/api/buildings").json()
check("楼栋数=3", len(buildings) == 3, str(len(buildings)))
bA, bB, bC = [b["id"] for b in buildings[:3]]

venues_a = c.get(f"/api/buildings/{bA}/venues").json()
check("汇智楼场地数=4", len(venues_a) == 4, str(len(venues_a)))
a101 = next(v for v in venues_a if v["room_no"] == "A101")
a202 = next(v for v in venues_a if v["room_no"] == "A202")
a301 = next(v for v in venues_a if v["room_no"] == "A301")
venues_b = c.get(f"/api/buildings/{bB}/venues").json()
b101 = next(v for v in venues_b if v["room_no"] == "B101")
b202 = next(v for v in venues_b if v["room_no"] == "B202")

# ---------- 2. 跨天档期：日视图两天都完整显示，周视图整条 ----------
r = c.get(f"/api/buildings/{bA}/venues/{a101['id']}/schedule?view=day&date={today(0):%Y-%m-%d}")
day0 = r.json()
cross_titles = [b["title"] for b in day0["bookings"] if "跨天" in b["title"]]
check("跨天场次当天日视图出现", any("产品封闭评审" in t for t in cross_titles), str(cross_titles))

r = c.get(f"/api/buildings/{bA}/venues/{a101['id']}/schedule?view=day&date={today(1):%Y-%m-%d}")
day1 = r.json()
cross_tomorrow = [b for b in day1["bookings"] if "产品封闭评审" in b["title"]]
check("跨天场次次日日视图仍完整出现（同一 id，不被切断）",
      len(cross_tomorrow) == 1 and cross_tomorrow[0]["start_at"].endswith("T14:00:00"),
      str(cross_tomorrow))
check("次日显示的跨天场次就是同一条记录",
      cross_tomorrow[0]["id"] == next(b["id"] for b in day0["bookings"] if "产品封闭评审" in b["title"]))

monday = (today(0) - timedelta(days=today(0).weekday())).strftime("%Y-%m-%d")
r = c.get(f"/api/buildings/{bA}/venues/{a101['id']}/schedule?view=week&date={monday}")
week = r.json()
check("周视图跨天场次只出现一次且完整",
      sum(1 for b in week["bookings"] if "产品封闭评审" in b["title"]) == 1)

# 第二条跨天：周五 18:00 -> 周六 09:00，跨周边界时两天视图都要有
fri = today(4 + (7 - today(0).weekday()) % 7)  # 下一个相对今天偏移5的日期由种子保证，这里直接用 offset
# 种子以“今天”为 offset 0，所以 offset5/6 直接取
r5 = c.get(f"/api/buildings/{bB}/venues/{b101['id']}/schedule?view=day&date={today(5):%Y-%m-%d}").json()
r6 = c.get(f"/api/buildings/{bB}/venues/{b101['id']}/schedule?view=day&date={today(6):%Y-%m-%d}").json()
id5 = [b["id"] for b in r5["bookings"] if "布展过夜" in b["title"]]
id6 = [b["id"] for b in r6["bookings"] if "布展过夜" in b["title"]]
check("布展跨天：周五/周六两天视图都出现且为同一条", id5 and id6 and id5 == id6, f"{id5} vs {id6}")

# ---------- 3. 冲突拦截：说清被谁占用 ----------
r = c.post("/api/bookings", json={
    "venue_id": a101["id"], "title": "撞车的会", "organizer": "测试员",
    "start_at": today(0, 9, 30).isoformat(), "end_at": today(0, 11, 0).isoformat(),
})
check("重叠时段被 409 拦截", r.status_code == 409, str(r.status_code))
check("冲突响应说明占用方与占用场次",
      r.status_code == 409 and "研发晨会" in r.json()["error"]["message"]
      and "行政部" in r.json()["error"]["message"]
      and r.json()["error"]["code"] == "time_conflict",
      r.text)

# 边界：紧贴前一场结束（10:30）起会，不算冲突
r = c.post("/api/bookings", json={
    "venue_id": a101["id"], "title": "紧接着的会", "organizer": "测试员",
    "start_at": today(0, 10, 30).isoformat(), "end_at": today(0, 11, 0).isoformat(),
})
check("半开区间边界相接不冲突", r.status_code == 201, r.text)

# 跨天撞车：新会议包住跨天场次的次日上午段
r = c.post("/api/bookings", json={
    "venue_id": a101["id"], "title": "撞跨天的会", "organizer": "测试员",
    "start_at": today(1, 9, 0).isoformat(), "end_at": today(1, 9, 30).isoformat(),
})
check("跨天场次次日上午仍能拦住撞车", r.status_code == 409
      and "产品封闭评审" in r.json()["error"]["message"], r.text)

# 装修中 / 停用场地不能下单
r = c.post("/api/bookings", json={
    "venue_id": a301["id"], "title": "想用装修房", "organizer": "测试员",
    "start_at": today(10, 9).isoformat(), "end_at": today(10, 10).isoformat(),
})
check("装修中场地下单被拦", r.status_code == 409 and "装修中" in r.json()["error"]["message"], r.text)

# 结束早于开始
r = c.post("/api/bookings", json={
    "venue_id": a101["id"], "title": "时间倒挂", "organizer": "测试员",
    "start_at": today(2, 11).isoformat(), "end_at": today(2, 10).isoformat(),
})
check("结束早于开始被拦", r.status_code == 400, r.text)

# ---------- 4. 删除场地：有未来档期不让删，说清原因 ----------
r = c.delete(f"/api/venues/{a101['id']}")
check("有未来档期的场地删除被 409 拦下", r.status_code == 409, r.text)
check("删除拦截信息含场次数量", r.status_code == 409
      and r.json()["error"]["code"] == "venue_has_future_bookings"
      and r.json()["error"]["future_count"] >= 1, r.text)

# 停用但只有已取消档期的 B202：未来无有效档期，可删
r = c.delete(f"/api/venues/{b202['id']}")
check("仅有已取消档期的场地允许删除", r.status_code == 204, r.text)

# ---------- 5. 跨楼栋访问被挡，且不是空白页 ----------
# 用 B 楼的路径去取 A 楼的场地
r = c.get(f"/api/buildings/{bB}/venues/{a101['id']}/schedule?view=day&date={today(0):%Y-%m-%d}")
check("跨楼栋看档期被 403 挡回", r.status_code == 403, r.text)
msg = r.json()["error"]["message"]
check("越权响应说明归属楼栋与当前楼栋",
      r.status_code == 403 and "汇智楼" in msg and "汇贤楼" in msg and "跨楼栋" in msg, msg)

# 不存在的楼栋
r = c.get("/api/buildings/9999/venues")
check("不存在楼栋返回 404 与解释", r.status_code == 404
      and "不存在" in r.json()["error"]["message"], r.text)

# 不存在的场地
r = c.get(f"/api/buildings/{bA}/venues/9999/schedule?view=day&date={today(0):%Y-%m-%d}")
check("不存在场地返回 404 与解释（非空白）", r.status_code == 404, r.text)

# 挂楼层时张冠李戴：A 楼场地挂 B 楼楼层
fb1 = next(f["id"] for b in buildings if b["id"] == bB for f in b["floors"] if f["level"] == 1)
r = c.post(f"/api/buildings/{bA}/venues", json={
    "building_id": bA, "floor_id": fb1, "name": "乱挂房", "room_no": "X1",
    "capacity": 5, "venue_type": "meeting_room", "facilities": [], "status": "available",
})
check("场地挂到别栋楼层被拦", r.status_code == 400 and "不属于楼栋" in r.json()["error"]["message"], r.text)

# ---------- 6. Redis：缓存命中 + 写后失效 ----------
r1 = c.get(f"/api/buildings/{bA}/venues/{a202['id']}/schedule?view=day&date={today(10):%Y-%m-%d}").json()
check("首次查询未命中缓存", r1["cached"] is False)
r2 = c.get(f"/api/buildings/{bA}/venues/{a202['id']}/schedule?view=day&date={today(10):%Y-%m-%d}").json()
check("再次查询命中 Redis 缓存", r2["cached"] is True)
r = c.post("/api/bookings", json={
    "venue_id": a202["id"], "title": "新预订触发缓存失效", "organizer": "测试员",
    "start_at": today(10, 9).isoformat(), "end_at": today(10, 10).isoformat(),
})
check("下单成功", r.status_code == 201, r.text)
r3 = c.get(f"/api/buildings/{bA}/venues/{a202['id']}/schedule?view=day&date={today(10):%Y-%m-%d}").json()
check("写后缓存失效，新场次立即可见",
      r3["cached"] is False and any("新预订" in b["title"] for b in r3["bookings"]), str(r3))

# ---------- 7. 占用锁：并发同抢一个空档，只能成一个 ----------
slot_start = today(20, 9)
slot_end = today(20, 10)
results = []


def grab(i):
    with TestClient(app) as cc:
        rr = cc.post("/api/bookings", json={
            "venue_id": a202["id"], "title": f"并发抢场#{i}", "organizer": f"用户{i}",
            "start_at": slot_start.isoformat(), "end_at": slot_end.isoformat(),
        })
        results.append(rr.status_code)


threads = [threading.Thread(target=grab, args=(i,)) for i in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join()
check("8 并发抢同一时段恰好 1 个成功", results.count(201) == 1 and results.count(409) == 7,
      str(sorted(results)))

# 越权取消
db = SessionLocal()
any_booking = db.query(models.Booking).join(models.Venue).filter(
    models.Venue.building_id == bA).first()
db.close()
r = c.post(f"/api/buildings/{bB}/bookings/{any_booking.id}/cancel")
check("跨楼栋取消档期被 403 挡回", r.status_code == 403 and "跨楼栋" in r.json()["error"]["message"], r.text)

print(f"\n通过 {len(PASS)} / 失败 {len(FAIL)}")
if FAIL:
    print("失败项:", FAIL)
    raise SystemExit(1)

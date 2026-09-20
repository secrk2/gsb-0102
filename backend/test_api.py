import os
import tempfile

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db", prefix="huitang_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["REDIS_URL"] = "memory://"
os.environ["SEED_ON_START"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import init_and_seed


@pytest.fixture(scope="session")
def client():
    init_and_seed()
    with TestClient(app) as c:
        yield c


def _today(offset=0):
    from datetime import date, timedelta

    return (date.today() + timedelta(days=offset)).isoformat()


def _dt(offset_days, hm):
    from datetime import datetime, timedelta

    h, m = map(int, hm.split(":"))
    return (
        (datetime.now() + timedelta(days=offset_days))
        .replace(hour=h, minute=m, second=0, microsecond=0)
        .isoformat(timespec="minutes")
    )


# ---------- 种子数据 ----------

def test_seed_counts(client):
    buildings = client.get("/api/buildings").json()
    assert len(buildings) == 3
    total_venues = 0
    for b in buildings:
        floors = client.get(f"/api/buildings/{b['id']}/floors").json()
        assert floors
        total_venues += len(
            client.get(f"/api/buildings/{b['id']}/venues").json()
        )
    assert total_venues == 10
    from app.models import Booking
    from app.database import SessionLocal
    with SessionLocal() as db:
        assert db.query(Booking).count() == 20


# ---------- 跨天档期：日/周视图都完整 ----------

def test_cross_day_booking_whole_in_day_views(client):
    # 种子第 1 条：场地1（id=1）今天 14:00 → 明天 10:30
    today = client.get(
        "/api/buildings/1/schedule", params={"view": "day", "day": _today(0)}
    ).json()
    b = next(x for x in today["bookings"] if x["id"] == 1)
    assert b["touched_dates"] == [_today(0), _today(1)]
    assert b["ends_after_range"] is True  # 日视图里完整带出次日才结束的信息

    tomorrow = client.get(
        "/api/buildings/1/schedule", params={"view": "day", "day": _today(1)}
    ).json()
    ids = [x["id"] for x in tomorrow["bookings"]]
    assert 1 in ids  # 明天上午那截不丢
    b2 = next(x for x in tomorrow["bookings"] if x["id"] == 1)
    assert b2["starts_before_range"] is True
    assert b2["start_at"].endswith("14:00")  # 开始时间仍是真实起点，未被截断到零点


def test_cross_day_booking_whole_in_week_view(client):
    week = client.get(
        "/api/buildings/1/schedule", params={"view": "week", "day": _today(0)}
    ).json()
    b = next(x for x in week["bookings"] if x["id"] == 1)
    # 周视图中是一条完整记录，覆盖两天，而不是被切成两条
    assert len([x for x in week["bookings"] if x["id"] == 1]) == 1
    assert set(b["touched_dates"]) == {_today(0), _today(1)}
    assert b["start_at"].endswith("14:00") and b["end_at"].endswith("10:30")


def test_week_starts_monday_and_7_days(client):
    week = client.get(
        "/api/buildings/2/schedule", params={"view": "week", "day": _today(2)}
    ).json()
    assert len(week["days"]) == 7
    from datetime import date

    # days[0] 必须是周一
    d0 = date.fromisoformat(week["days"][0])
    assert d0.weekday() == 0


# ---------- 冲突拦截 ----------

def test_conflict_blocked_with_occupier(client):
    # 场地1 已有今天 14:00→明天10:30；再下今天 16:00→18:00 应撞
    r = client.post(
        "/api/buildings/1/venues/1/bookings",
        json={
            "title": "撞车测试",
            "booker": "测试员",
            "start_at": _dt(0, "16:00"),
            "end_at": _dt(0, "18:00"),
        },
    )
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "time_conflict"
    assert err["details"]["occupier"]["title"] == "产品联合评审（跨天连场）"
    assert "测试员" not in err["message"] or err["details"]["occupier"]["booker"]
    assert "王敏" in err["message"]  # 说清被谁占用


def test_back_to_back_allowed(client):
    # 紧贴边界（前一场 11:00 结束，新场 11:00 开始）允许：半开区间不冲突
    r = client.post(
        "/api/buildings/1/venues/2/bookings",  # 路演大厅 09-11 有晨会
        json={
            "title": "紧接开场",
            "booker": "测试员",
            "start_at": _dt(0, "11:00"),
            "end_at": _dt(0, "12:00"),
        },
    )
    assert r.status_code == 201, r.text


def test_renovating_venue_rejects_booking(client):
    # 场地4 = 第二会议室（装修中）
    r = client.post(
        "/api/buildings/1/venues/4/bookings",
        json={
            "title": "装修期撞约",
            "booker": "测试员",
            "start_at": _dt(5, "10:00"),
            "end_at": _dt(5, "11:00"),
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "venue_unavailable"


# ---------- 删场地保护 ----------

def test_delete_venue_with_future_bookings_blocked(client):
    # 场地1 有未来档期
    r = client.delete("/api/buildings/1/venues/1")
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "venue_has_future_bookings"
    assert err["details"]["count"] >= 1
    assert client.get("/api/buildings/1/venues").status_code == 200
    assert any(v["id"] == 1 for v in client.get("/api/buildings/1/venues").json())


def test_delete_clean_venue_ok(client):
    # 场地7 = 灯塔培训室：停用且无任何档期
    r = client.delete("/api/buildings/1/venues/7")
    # 注意场地7在楼栋2（汇智楼）
    assert r.status_code in (403, 404)
    r = client.delete("/api/buildings/2/venues/7")
    assert r.status_code == 204, r.text
    assert all(v["id"] != 7 for v in client.get("/api/buildings/2/venues").json())


def test_venue_only_past_bookings_can_delete(client):
    # 场地6 云帆会议室：未来档期有 → 先拦；取消未来档期后只剩历史 → 可删
    r = client.delete("/api/buildings/2/venues/6")
    assert r.status_code == 409
    # 找到它的未来档期并全部取消
    week = client.get(
        "/api/buildings/2/schedule",
        params={"view": "week", "day": _today(30), "venue_id": 6},
    ).json()
    # 直接按列表找
    sched = client.get(
        "/api/buildings/2/schedule",
        params={"view": "week", "day": _today(0), "venue_id": 6},
    ).json()
    for b in sched["bookings"]:
        assert client.post(f"/api/buildings/2/bookings/{b['id']}/cancel").status_code == 204
    # 下一周可能还有档期（offset 3 的已在本周内取决于锚点；offset 3 在本周）
    for woff in (7, 14, 21, 28):
        sched = client.get(
            "/api/buildings/2/schedule",
            params={"view": "week", "day": _today(woff), "venue_id": 6},
        ).json()
        for b in sched["bookings"]:
            client.post(f"/api/buildings/2/bookings/{b['id']}/cancel")
    r = client.delete("/api/buildings/2/venues/6")
    assert r.status_code == 204, r.text


# ---------- 跨楼栋拦截 ----------

def test_unknown_building_404_not_blank(client):
    r = client.get("/api/buildings/999/schedule", params={"day": _today(0)})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "building_not_found"
    assert "999" in r.json()["error"]["message"]


def test_cross_building_venue_schedule_blocked(client):
    # 场地1 属于楼栋1，去楼栋2 的档期里查它
    r = client.get(
        "/api/buildings/2/schedule",
        params={"day": _today(0), "venue_id": 1},
    )
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "cross_building_denied"
    assert "别的楼栋" in err["message"]


def test_cross_building_booking_blocked(client):
    r = client.post(
        "/api/buildings/2/venues/1/bookings",
        json={
            "title": "跨楼下单",
            "booker": "测试员",
            "start_at": _dt(20, "09:00"),
            "end_at": _dt(20, "10:00"),
        },
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "cross_building_denied"


def test_cross_building_venue_delete_blocked(client):
    # 场地8 在楼栋2，试图从楼栋1 删除
    r = client.delete("/api/buildings/1/venues/8")
    assert r.status_code == 403


# ---------- Redis 缓存 ----------

def test_schedule_cache_hit_and_invalidation(client):
    params = {"view": "day", "day": _today(10)}
    r1 = client.get("/api/buildings/1/schedule", params=params)
    assert r1.json()["cached"] is False
    r2 = client.get("/api/buildings/1/schedule", params=params)
    assert r2.json()["cached"] is True

    # 新建档期 → 缓存失效
    r = client.post(
        "/api/buildings/1/venues/2/bookings",
        json={
            "title": "缓存验证场",
            "booker": "测试员",
            "start_at": _dt(10, "09:00"),
            "end_at": _dt(10, "10:00"),
        },
    )
    assert r.status_code == 201
    r3 = client.get("/api/buildings/1/schedule", params=params)
    assert r3.json()["cached"] is False
    assert any(b["title"] == "缓存验证场" for b in r3.json()["bookings"])


# ---------- 场地档案 ----------

def test_venue_crud_and_validation(client):
    floors = client.get("/api/buildings/3/floors").json()
    fid = floors[0]["id"]
    r = client.post(
        "/api/buildings/3/venues",
        json={
            "floor_id": fid,
            "name": "新建测试室",
            "door_plate": "T01",
            "capacity": 25,
            "venue_type": "会议室",
            "equipment": ["投影", "白板"],
            "status": "可订",
        },
    )
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    assert r.json()["building_name"] == "远见楼"

    r = client.put(
        f"/api/buildings/3/venues/{vid}", json={"status": "停用", "capacity": 30}
    )
    assert r.status_code == 200 and r.json()["status"] == "停用"

    # 非法枚举
    r = client.post(
        "/api/buildings/3/venues",
        json={
            "floor_id": fid,
            "name": "坏数据",
            "door_plate": "T02",
            "capacity": 1,
            "venue_type": "舞厅",
            "equipment": [],
        },
    )
    assert r.status_code == 422
    r = client.post(
        "/api/buildings/3/venues",
        json={
            "floor_id": fid,
            "name": "坏设备",
            "door_plate": "T03",
            "capacity": 1,
            "venue_type": "会议室",
            "equipment": ["咖啡机"],
        },
    )
    assert r.status_code == 422

    # 同楼层门牌重复
    r = client.post(
        "/api/buildings/3/venues",
        json={
            "floor_id": fid,
            "name": "重复门牌",
            "door_plate": "T01",
            "capacity": 1,
            "venue_type": "会议室",
            "equipment": [],
        },
    )
    assert r.status_code == 409

    # 把楼层填成别的楼栋的楼层
    other_fid = client.get("/api/buildings/1/floors").json()[0]["id"]
    r = client.post(
        "/api/buildings/3/venues",
        json={
            "floor_id": other_fid,
            "name": "跨楼挂靠",
            "door_plate": "T04",
            "capacity": 1,
            "venue_type": "会议室",
            "equipment": [],
        },
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "floor_mismatch"

    assert client.delete(f"/api/buildings/3/venues/{vid}").status_code == 204


def test_concurrent_double_booking_lock(client):
    """两个线程同时给同一场地下同一时段：锁 + 查重保证只成功一个。"""
    import threading
    from app.database import SessionLocal
    from app.schemas import BookingCreate
    from app import services

    results = []

    def worker():
        db = SessionLocal()
        try:
            data = BookingCreate(
                title="并发抢订",
                booker=f"线程{threading.get_ident() % 100}",
                start_at=_dt(40, "09:00"),
                end_at=_dt(40, "11:00"),
            )
            try:
                services.create_booking(db, 1, 2, data)  # 场地2 此时段空闲
                results.append("ok")
            except services.ApiError as e:
                results.append(e.code)
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == 1, results
    assert "time_conflict" in results

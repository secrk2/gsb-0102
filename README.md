# 汇堂 · 园区场地档期平台

园区场地预订从「前台拿本子记」搬到线上。本轮交付三块：

- **楼栋与楼层**：场地挂在「楼栋 → 楼层」两级结构下
- **场地档案**：门牌号、容纳人数、场地类型（会议室 / 路演厅 / 培训室 / 活动场地）、
  配套设备（投影 / 视频会议 / 白板）、状态（可订 / 装修中 / 停用）
- **档期与占用**：日视图、周视图两种看法；一个时段只能被一个场次占用，
  撞单会被拦下并说清被谁占用；跨天档期（今天下午→明天上午）在两种视图上
  都是一条完整连续的记录，不拆段、不丢失

技术栈：Vue 3 + Vite ｜ Python + FastAPI + SQLAlchemy ｜ MySQL 8 ｜ Redis 7
（占用分布式锁 + 档期查询缓存）。

## 一键启动（compose）

```bash
docker compose up -d --build
```

四个容器一次带起：mysql、redis、backend（FastAPI）、web（Nginx 托管前端并反代 /api）。
启动后访问：

- 平台入口： **http://localhost:8102**
- 接口健康检查： http://localhost:8102/api/health

后端启动时会自动建表并写入种子数据：**3 个楼栋、10 间场地、20 条档期**
（其中含 2 条跨天档期，如「产品联合评审（跨天连场）」今天 14:00 → 明天 10:30；
档期以启动当天为锚点，保证开箱即有未来数据可演示）。种子幂等，已有数据时跳过。

重置数据：`docker compose down -v && docker compose up -d --build`

## 业务规则与实现要点

| 规则 | 行为 |
| --- | --- |
| 单一时段占用 | 下单走 Redis 分布式锁（`lock:venue:{id}`，NX + token 校验释放）串行化「查重+写入」，数据库按半开区间 `start < 对方end AND end > 对方start` 判撞，并发抢同一时段只有一单成功 |
| 撞单提示 | 返回 409 `time_conflict`，消息中带占用场次名称、预订人、起止时间，前端弹窗直接展示「当前占用方」卡片 |
| 跨天完整 | 查询用半开区间与窗口相交，命中即返回**整条**档期；响应附 `touched_dates` / `starts_before_range` / `ends_after_range`，前端在日/周视图画成连续条，用 « » 标出延伸到视图外的部分 |
| 装修中 / 停用 | 非「可订」场地拒绝下单（409 `venue_unavailable`），档期行用斜纹底 + 状态标识区分 |
| 删除保护 | 场地名下只要还有未结束（`end_at > now`）的有效档期就拦下（409 `venue_has_future_bookings`），返回数量与最早一条档期详情；只剩历史档期不拦 |
| 跨楼栋隔离 | 所有接口以楼栋为作用域：陌生楼栋 ID 返回 404 并解释原因（不给空白页）；操作别楼栋的场地/档期返回 403 `cross_building_denied`，消息点名该场地实际属于哪栋楼 |
| 档期缓存 | 日/周查询结果写 Redis（TTL 60s，key 含楼栋/视图/日期/筛选），任何档期或场地变更按 `schedule:{buildingId}:*` 模式失效 |

## 本地开发（不用 Docker）

后端（无 MySQL/Redis 时可用 SQLite + 进程内 KV 跑通全部逻辑）：

```bash
cd backend
python3 -m venv --without-pip .venv && .venv/bin/python get-pip.py   # 视环境而定
.venv/bin/pip install -r requirements.txt
export DATABASE_URL="sqlite:///./huitang.db"
export REDIS_URL="memory://"
.venv/bin/uvicorn app.main:app --reload --port 8000
.venv/bin/pytest -q          # 17 项业务规则测试
```

前端：

```bash
cd frontend
npm install
npm run dev                  # http://localhost:8102，已配 /api 代理到 8000
```

## 目录结构

```
├── docker-compose.yml          # mysql + redis + backend + web，入口 8102
├── backend/
│   ├── app/main.py             # FastAPI 入口、统一业务错误结构
│   ├── app/models.py           # Building / Floor / Venue / Booking
│   ├── app/services.py         # 冲突判定、删除保护、跨楼栋、日/周聚合
│   ├── app/redis_client.py     # 占用锁 + 缓存（redis:// 或 memory://）
│   ├── app/seed.py             # 3 楼栋 / 10 场地 / 20 档期
│   └── test_api.py             # 业务规则测试（含并发双占）
└── frontend/
    ├── src/views/ScheduleView.vue  # 日/周档期甘特板，跨天连续渲染
    ├── src/views/VenuesView.vue    # 场地档案 CRUD + 删除拦截
    └── nginx.conf                  # SPA 路由 + /api 反代
```

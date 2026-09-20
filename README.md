# 汇堂 · 园区场地档期平台

园区场地的档案与档期管理，替代前台手工登记本。

- **页面**：Vue 3 + Vite（nginx 托管，`/api` 反代 FastAPI）
- **服务**：Python 3.12 + FastAPI + SQLAlchemy 2
- **存储**：MySQL 8.4（场地、楼栋楼层、档期）
- **锁与缓存**：Redis 7（下单占用锁、档期查询缓存）
- **部署**：docker compose 一次带起，访问入口 **http://localhost:8102**

## 快速开始

```bash
docker compose up -d --build
```

首次启动会自动：建表 → 灌入种子数据（**3 个楼栋、10 间场地、20 条档期，含 2 条跨天**）→ 起 API。

种子脚本幂等，重复执行不会产生重复数据：

```bash
docker compose exec backend python -m app.seed
```

打开 http://localhost:8102 ：左侧楼栋树（楼栋 → 楼层 → 场地），右侧档期看板。

## 功能对照（本轮范围）

### 场地档案
- 场地挂在楼栋下的具体楼层，记录**门牌号、容纳人数、场地类型、配套设备、状态**
- 类型：会议室 / 路演厅 / 培训室 / 活动场地
- 设备：投影 / 视频会议 / 白板
- 状态：可订 / 装修中 / 停用（非「可订」状态不能登记新档期）
- 同楼层门牌号唯一；场地不能挂到别的楼栋的楼层下

### 档期与占用
- **日视图**：08:00–22:00 时间轴，点击空白时段直接下单；跨天场次在当天标「跨天起 ▶」，次日标「◀ 跨天续」，两天显示的是**同一条记录**，不切断、不丢失
- **周视图**：横向甘特，每列是当天 08:00–22:00；跨天场次是**一条连续贯穿多列的色带**（紫色，标「跨N天」），夜间折叠为列边界
- 一个时段同一场地只能被一个场次占用，重叠即 409，响应里直接说清：
  > 时段冲突：… 已被「研发晨会」（占用方：行政部，2026-09-20 09:00 ~ 10:30）占用，请换个时段。
- 时间采用半开区间 `[start, end)`，紧接上一场结束时间开始不算撞
- **删场地拦截**：名下还有未结束档期时返回 409，说明剩余场次数与最早一场：
  > 场地「第一会议室」名下还有 2 场未结束的档期，最早一场「产品封闭评审（跨天）」开始于 2026-09-20 14:00，请先取消这些档期后再删除场地。
- 已取消的档期不计入拦截；场地删除后其历史档期保留（外键置空，保留场地名快照）
- **跨楼栋拦截**：所有档期查询/取消都必须带楼栋归属校验，越权返回 403 并说明归属：
  > 场地「第一会议室」属于汇智楼，不属于当前楼栋「汇贤楼」，不能跨楼栋查看或操作其档期。请切换到对应楼栋后再试。
- 楼栋/场地不存在时返回 404 + 中文解释，前端以错误横幅展示，**不会出现空白页**

### 楼栋与楼层
- 楼栋有名称与唯一编号；楼层含楼层数（支持地下，如 -1）与显示名
- 楼栋树下可新增楼栋、楼层，楼层下可新建场地

### Redis：占用锁 + 缓存
- 下单时对场地维度加分布式锁 `lock:venue:{id}`（SET NX + TTL，WATCH 事务释放），
  同时 DB 行锁 `SELECT … FOR UPDATE` + 区间冲突查询兜底；实测 **8 个并发抢同一时段恰好 1 个成功**
- 档期查询结果写缓存 `schedule:venue:{id}:{view}:{anchor}`（默认 30 秒），下单/取消/删场地后按场地失效

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | API/Redis 健康检查 |
| GET/POST | `/api/buildings` | 楼栋列表（含楼层）/ 新建楼栋 |
| POST | `/api/buildings/{id}/floors` | 新建楼层 |
| GET/POST | `/api/buildings/{id}/venues` | 楼栋下场地列表 / 新建场地 |
| PATCH/DELETE | `/api/venues/{id}` | 改档案 / 删场地（有未来档期会 409） |
| GET | `/api/buildings/{bid}/venues/{vid}/schedule?view=day\|week&date=YYYY-MM-DD` | 日/周档期（跨天完整返回） |
| POST | `/api/bookings` | 登记档期（撞单 409，说明被谁占用） |
| POST | `/api/buildings/{bid}/bookings/{id}/cancel` | 取消档期（跨楼栋 403） |

所有业务错误统一信封：`{"error": {"code": "...", "message": "中文原因", ...}}`。

## 目录结构

```
├── docker-compose.yml      # mysql + redis + backend + frontend，8102 入口
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── verify_scenarios.py # 27 项关键场景验证（无需 Docker，见下）
│   └── app/
│       ├── main.py         # FastAPI 路由 + 统一错误处理
│       ├── services.py     # 锁/冲突/跨天查询/删除拦截/越权校验
│       ├── models.py       # Building/Floor/Venue/Booking
│       ├── schemas.py      # pydantic 校验
│       ├── redis_client.py # 锁释放（WATCH 事务）+ 缓存客户端
│       └── seed.py         # 种子数据（幂等）
└── frontend/
    ├── Dockerfile          # node 构建 + nginx 托管
    ├── nginx.conf          # SPA fallback + /api 反代
    └── src/
        ├── App.vue
        ├── api.js
        └── components/
            ├── BuildingTree.vue       # 楼栋/楼层/场地树
            ├── ScheduleBoard.vue      # 日/周视图（跨天连续渲染）
            ├── VenueFormModal.vue     # 场地档案 + 删除
            ├── BookingModal.vue       # 登记档期（冲突说明）
            └── BookingDetailModal.vue # 档期详情/取消
```

## 无 Docker 本地调试

后端可用 SQLite + fakeredis（同一套模型与逻辑，仅本地调试用；生产固定 MySQL + Redis）：

```bash
python -m venv .venv && .venv/bin/pip install -r backend/requirements.txt fakeredis httpx
cd backend
DATABASE_URL="sqlite:///./dev.db" REDIS_URL="fakeredis://" .venv/bin/python -m app.seed
DATABASE_URL="sqlite:///./dev.db" REDIS_URL="fakeredis://" \
  .venv/bin/uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend && npm install && npm run dev   # /api 代理到 localhost:8000
```

关键场景自动化验证（27 项，覆盖跨天两种视图、冲突文案、删除拦截、跨楼栋、缓存失效、并发锁）：

```bash
cd backend
DATABASE_URL="sqlite:////tmp/t.db" REDIS_URL="fakeredis://" .venv/bin/python verify_scenarios.py
```

前端测试（14 项跨天日/周几何纯函数单测 + 11 项 jsdom 组件交互测试）：

```bash
cd frontend
npm install        # 组件测试需要 jsdom / @vue/test-utils（devDependencies）
npm test
```

## 关键设计说明

- **跨天为什么不会断**：档期是一行带完整起止的记录，视图只做「区间与窗口重叠」查询
  （`start_at < 窗口末 AND end_at > 窗口首`），日视图每天独立命中同一行；周视图前端按各天
  08:00–22:00 窗口求宽度并拼接成连续带，不做任何按天拆行。
- **并发安全双保险**：Redis 锁把同一场地的下单请求串行化（防前端双击/多人同抢），
  事务内再对场地行 `SELECT … FOR UPDATE` 后做区间重叠查询兜底；即使绕过锁也撞不进去。
- **删除与历史**：档期是业务凭证，不随场地物理删除；场地删了，旧档期仍可通过场地名快照追溯。

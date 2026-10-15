# TravelMate AI — v0.2

**v0.1 骨架**:账户系统 + 用户偏好 + 基础 Web Shell + 本地城市搜索 + MySQL 持久化。
**v0.2 城市旅游信息**:城市搜索历史 + 高德实时天气/穿衣建议 + 景点 + 美食 + 可拖动双栏布局。

v0.2 仍**不做** AI Chat、Conversation、Agent Tool Calling、RAG —— 留给 v0.3 / v0.4。

核心文件 **88 个**(v0.1 的 48 + v0.2 新增 40):根配置 2 + 前端 47 + 后端 39(空 `__init__.py`、lock 文件不计入)。

---

## v0.2 新增能力

| 能力 | 实现要点 |
|---|---|
| 城市搜索历史 | `city_view_history` 表,`UNIQUE(user_id, adcode)` → 重复选同城只更新 `viewed_at`,不产生重复 |
| Recent Searches | 搜索框聚焦且无关键词时,下拉显示最近 10 个城市的本地历史 |
| 实时天气 + 穿衣建议 | 高德天气**请求两次**(`base` 拿实时、`all` 拿预报)后合并;穿衣建议按温度阈值 + 天气文本(含"雨"补雨具)在本地生成,不调用 DeepSeek |
| 景点 Tab(默认) | 默认 10 个用高德**类别码 `types=110000`** 取(不能按关键词"景点",否则会混进写字楼);关键词搜索切到 `page_size=20` 并支持 Load More |
| 景点详情 | 照片 / 地址 / 价格·门票 / 标签;`location` 后台保留但 UI 不展示经纬度 |
| 美食 Tab(首次点击才加载) | DeepSeek 生成 10 种代表美食(JSON),再对每种查高德餐饮 POI 取 2 家真实餐厅;封面取真实 POI 照片 |
| 美食搜索 | 输入"火锅"等关键词 → 切换为餐厅结果模式,支持 Load More |
| 餐厅详情 | 人均 / 地址 / 评分 / 预订电话,缺失一律"暂无信息" |
| 可拖动双栏 | `el-splitter`,默认约 80% 城市区 / 20% AI 区(AI 区 v0.2 仍是占位) |

**两条硬约束**(§36/§37):第三方 API 没有的数据一律 `null` → 前端显示"暂无信息",**绝不让 LLM 编造餐厅价格/评分/地址/电话**;图片只用网络 URL,服务器不下载、不落盘。

---

## 0. 快速启动

本机依赖与数据库都已就绪,只需**两个窗口**(保持窗口开着即为运行中,Ctrl+C 停止):

```
start-backend.cmd      → 后端 http://127.0.0.1:8000   (接口文档 /docs)
start-frontend.cmd     → 前端 http://localhost:5173
```

双击即可;也可以在任意终端里执行。`.cmd` 只是启动器,真正的逻辑在配套的 `.ps1` 里
(用 `-ExecutionPolicy Bypass` 绕开"系统禁止运行脚本"的默认策略)。

想直接跑 PowerShell 版本时:

```powershell
.\start-backend.ps1
# 若提示"禁止运行脚本":
powershell -ExecutionPolicy Bypass -File .\start-backend.ps1
```

**本机三个环境注意事项**

- 系统 PATH 里**没有 `node`**。`start-frontend.ps1` 会自动回退到 DSH 桌面端内置的 Node + pnpm。
  想用标准的 `npm install` / `npm run dev`,先装 Node.js LTS(≥20)。
- `backend\.venv` 里的依赖已装好,但这个 venv **没有 pip**(创建时受运行环境限制)。
  只运行不受影响;要装新依赖,请删掉 `.venv` 后在**普通终端**重建 —— `python -m venv .venv`
  会正常带上 pip,再按第 2 节安装即可。
- MySQL80 服务是"自动"启动类型,开机即在运行;`travelmate` 库与账号已建好,密码写在 `.env`。

---

## 1. 环境要求

| 组件 | 版本 |
|---|---|
| Node.js | ≥ 20(vite 8 要求) |
| Python | ≥ 3.11(开发使用 3.13) |
| MySQL | 8.0 |

---

## 2. 后端启动

```bash
cd backend

# 1) 虚拟环境 + 依赖
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2) 建库建用户(用有权限的账号执行一次)
#    CREATE DATABASE travelmate CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
#    CREATE USER 'travelmate'@'localhost' IDENTIFIED BY '你的密码';
#    GRANT ALL PRIVILEGES ON travelmate.* TO 'travelmate'@'localhost';

# 3) 配置
copy ..\.env.example ..\.env    # 然后填 MYSQL_PASSWORD 与 JWT_SECRET

# 4) 建表
python -m app.db.init_db        # 输出 created tables: user_preferences, users

# 5) 启动
uvicorn app.main:create_app --factory --reload --port 8000
```

`create_app` 用工厂模式暴露,导入模块不会连数据库;`init_db()` 只在真正构造应用时执行。

自检:

```bash
curl http://127.0.0.1:8000/health      # {"status":"ok"}
```

---

## 3. 前端启动

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # 产物在 dist/
npm run preview
```

vite 开发服务器把 `/api` 与 `/health` 代理到 `http://127.0.0.1:8000`,
所以浏览器眼里只有 5173 一个源,HttpOnly Cookie 能正常携带,
前端也就能统一请求 `/api/v1/...` —— v0.2 / v0.3 不需要改请求习惯。

---

## 4. 测试

```bash
cd backend
python -m pytest tests -q
```

11 个测试(认证 6 + 偏好 5)全部跑在内存 SQLite 上,不需要 MySQL。

v0.2 后共 **33 个测试**(v0.1 的 11 + 城市历史 4 + 天气 4 + 景点 6 + 美食 8)。高德与 DeepSeek 全部 mock,不消耗真实 API quota。

---

## 5. 认证方案

```
JWT(HS256) → HttpOnly Cookie
Cookie: HttpOnly=true, SameSite=Lax, Secure=(APP_ENV=="production")
前端 Axios: withCredentials=true,永远不读 JWT
```

## 6. API

统一前缀 `/api/v1`。

| Method | Path | 登录 | 功能 |
|---|---|:--:|---|
| POST | `/auth/register` | 否 | 注册(同时建立登录态) |
| POST | `/auth/login` | 否 | 登录 |
| POST | `/auth/logout` | 是 | 退出(清 Cookie) |
| GET | `/auth/me` | 是 | 当前用户(刷新恢复登录态) |
| GET | `/preferences/me` | 是 | 获取偏好(没保存过返回空结构) |
| PUT | `/preferences/me` | 是 | 保存/修改偏好,并置 onboarding_completed |
| POST | `/preferences/skip` | 是 | 跳过 Onboarding(不伪造偏好) |
| GET | `/cities/history` | 是 | 最近搜索的城市(最多 10,倒序) |
| POST | `/cities/history` | 是 | 记录一次城市浏览(同城 upsert) |
| GET | `/weather?adcode=` | 是 | 实时天气 + 预报合并 + 穿衣建议 |
| GET | `/attractions` | 是 | 景点列表(`city_name`/`adcode`/`keyword`/`page`/`page_size`) |
| GET | `/attractions/{poi_id}` | 是 | 景点详情(含 `location`,UI 不展示) |
| GET | `/food/featured` | 是 | 10 种代表美食 + 每种最多 2 家真实餐厅 |
| GET | `/food/restaurants` | 是 | 按关键词搜索餐厅(分页) |
| GET | `/food/restaurants/{poi_id}` | 是 | 餐厅详情(人均/地址/评分/电话) |
| GET | `/health` | 否 | 健康检查 |

外部 API 备注:高德个人 Key 有 **QPS 限制**,连续快速请求会返回 `status=0`(看起来像"无数据");
`amap_client` 已内置退避重试,`food/featured` 的 10 路查询用 `Semaphore(3)` + 间隔控流。

---

## 7. 分层约定

```
frontend/src  router / api / stores / views / components / constants / utils / data / styles
backend/app   api(router, deps, routes) / services / schemas / models / db / core
```

- 路由只负责 HTTP 语义,业务逻辑在 `services`;
- 偏好选项只在 `constants/preferences.js` 定义一次;
- 城市索引只在 `data/cities.json`,搜索算法只在 `utils/citySearch.js`;
- `/onboarding` 同时是"首次填写"和"已登录用户修改偏好"的唯一入口
  (Sidebar 的 Preferences 指向它),避免两套偏好表单走偏;
- 城市上下文只有 `stores/city.js` 的 `openCity()` 一个入口(内部并行记录历史 + 拉天气),
  HomeView 不自己拼 API;
- 缺失值统一走 `utils/display.js`,不在各组件里各写一套兜底。

**为 v0.3 做的架构准备**:v0.2 已形成四个可复用 Service ——
`preference_service` / `weather_service` / `attraction_service` / `food_service`。
v0.3 的 Agent Tool **必须调用这些现成 Service,不允许重写一套查询逻辑**。

后续版本增量落点:

```
v0.3  conversation / chat / agent  → AiPlaceholder 升级为真正的 ChatPanel,Agent Tool 复用 v0.2 的 Service
v0.4  retrieval / rag
```

---

## 8. 安全

- 密码只存 bcrypt 哈希(`$2b$12$...`);
- `JWT_SECRET`、MySQL 密码、`AMAP_API_KEY`、`DEEPSEEK_API_KEY` 只存在于 `.env`,
  `.env` 已被 `.gitignore` 忽略;`.env.example` 里全是 `change_me` 占位符;
- **前端绝不持有任何第三方 Key**,高德与 DeepSeek 只由后端调用;
- 数据库异常统一降级为 `500 {"detail":"服务器暂时不可用"}`,外部 API 失败降级为 `502` + 中文提示,
  不向前端暴露 traceback / SQLAlchemyError / Key / 完整 URL。

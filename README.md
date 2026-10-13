# TravelMate AI — v0.1

v0.1 只搭骨架:**账户系统 + 用户偏好 + 基础 Web Shell + 本地城市搜索 + MySQL 持久化**。
明确不接高德、不接 DeepSeek、不做 Agent、不做 RAG —— 这些留给 v0.2 / v0.3 / v0.4 增量加入。

核心文件 **48 个**:根配置 2 + 前端 26 + 后端 20(空 `__init__.py` 不计入)。

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
| GET | `/health` | 否 | 健康检查 |

---

## 7. 分层约定(为 v0.2+ 预留)

```
frontend/src  router / api / stores / views / components / constants / utils / data / styles
backend/app   api(router, deps, routes) / services / schemas / models / db / core
```

- 路由只负责 HTTP 语义,业务逻辑在 `services`;
- 偏好选项只在 `constants/preferences.js` 定义一次;
- 城市索引只在 `data/cities.json`,搜索算法只在 `utils/citySearch.js`;
- `/onboarding` 同时是"首次填写"和"已登录用户修改偏好"的唯一入口
  (Sidebar 的 Preferences 指向它),避免两套偏好表单走偏。

后续版本增量落点:

```
v0.2  city / weather / attractions / food  → 前端加 api+stores+components,后端加 routes+services
v0.3  conversation / chat / agent          → AiPlaceholder 升级为真正的 ChatPanel
v0.4  retrieval / rag
```

---

## 8. 安全

- 密码只存 bcrypt 哈希(`$2b$12$...`);
- `JWT_SECRET` 与 MySQL 密码只存在于 `.env`,`.env` 已被 `.gitignore` 忽略;
- 数据库异常统一降级为 `500 {"detail":"服务器暂时不可用"}`,不向前端暴露 traceback / SQLAlchemyError。

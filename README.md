# TravelMate AI — v0.3.1

**v0.1 骨架**:账户系统 + 用户偏好 + 基础 Web Shell + 本地城市搜索 + MySQL 持久化。
**v0.2 城市旅游信息**:城市搜索历史 + 高德实时天气/穿衣建议 + 景点 + 美食 + 可拖动双栏布局。
**v0.3 完整 AI Travel Agent**:DeepSeek Chat + 多 Conversation + 多城市 + 会话隔离 + Tool Calling + Agent Activity。
**v0.3.1 中英双语国际化**:全站 `中文 / English` 切换 + 双语实体展示 + 英文搜索转中文查真实 POI + 翻译缓存。

v0.3.1 仍**不做** LangChain / Milvus / RAG —— 留给 v0.4。

核心文件 **131 个**(v0.3 的 114 + v0.3.1 新增 16 + 国际词典数据文件 1):根配置 2 + 前端 67 + 后端 62
(空 `__init__.py`、lock 文件不计入)。

---

## v0.3.1 新增能力(中英双语)

| 能力 | 实现要点 |
|---|---|
| 语言切换 | 顶部右侧 `中文 \| English`(未登录页固定在右上角);**即时切换、刷新保持、不重置**当前城市 / Tab / Splitter / 会话 / 消息 |
| 全站文案 i18n | `vue-i18n` + `el-config-provider`;**zh-CN 与 en-US 的 key 完全一致**(16 个命名空间);英文模式零未授权中文 |
| 城市双语 | 168 个城市补齐 `city_name_en` / `province_en` / `pinyin_initials` / `aliases_en`;中英文、拼音、首字母、异写都能搜到同一城市,展示为 `Chengdu (成都)` |
| 英文搜索真查高德 | `ancient town` → 词典/翻译解析成 `古镇` → 用**中文关键词 + 原 `types`** 查高德;查不到就返回受控 422 `query.unrecognized`,**绝不悄悄退回默认 Top10** |
| POI 双语 | 名称/地址/标签带 `*_en` 与 `*_source`(`verified`/`model`/`transliterated`/`fallback`);`poi_id`、经纬度、评分、价格、电话、图片**永不被翻译或改写** |
| 翻译缓存 | MySQL `entity_translations`,`UNIQUE(provider, entity_key, field_name, target_locale, source_hash, translation_version)`;原文变则 hash 变、自动失效 |
| 天气/穿衣 codes | 后端返回 `weather_code` 与 `clothing_advice_codes`(枚举),前端按语言渲染;数字原值不动 |
| Activity codes | `code` + `params`(如 `agent.weather_found` + `{city_name}`),前端按语言渲染;`text` 保留做兼容 |
| Agent 按语言生成 | 中/英分别组系统提示词;英文回答自然英文,专有名词用 `English (中文)`;**历史消息永不改写** |

**两条红线**:①拿不到可信英文名时明确降级(`fallback`),**不编造官方译名**;②`poi_id` / `adcode` / `conversation_id` / Tool 名等业务标识**不本地化**。

---

## v0.3 新增能力

| 能力 | 实现要点 |
|---|---|
| 真实 AI Chat | `ChatPanel` 取代 `AiPlaceholder`;**未选城市时 Chat 占主页主要区域**,选中城市后才切到 80/20 Splitter |
| 多 Conversation | 数量无业务限制;数据库 `conversations` + `conversation_cities`(0 / 1 / 多城市均可),可随时改当前会话城市 |
| Conversation Drawer | **只存在于 AI 区内部**且默认隐藏;网站 Sidebar **始终不出现**对话历史 |
| 会话记忆规则 | Preferences **跨会话共享**(通过 Tool 读取);Message History **严格按 `conversation_id` 隔离** |
| Agent Tool Calling | 固定 4 个工具:`get_user_preferences` / `get_weather` / `search_attractions` / `search_food`,**全部复用 v0.2 的 service,不重写业务逻辑** |
| 工具城市上下文 | 工具只在**当前 Conversation 的 cities** 里找城市;找不到返回受控提示,绝不偷偷改会话城市 |
| Agent Activity | 只显示**实际执行过**的工具(✓/●/!),不显示 Chain-of-Thought,不伪造未发生的调用 |
| 消息持久化 | 数据库只存最终 `user` / `assistant`;Agent 内部的 tool-call / tool 消息**只在单次请求内传递,不落库** |
| Recommended Prompts | 点击后填入 ChatInput,**不自动发送**;没有 active 会话时首次发送会自动创建一个 `cities=[]` 的会话 |

**Agent 行为红线**(§43):`user_id` 只能来自服务端,模型的工具 Schema 里没有它;dispatcher 白名单派发,禁止 `eval`;
工具没返回的价格/评分/地址/电话一律"暂无信息",**绝不让模型编造**;整体失败时**不写虚假的 assistant 成功消息**。

> 提示词实测要点:系统提示词里明确"具体城市的天气/景点/餐厅事实必须先调工具"后,
> 事实类问题 4/4 触发工具、通用常识 2/2 不触发工具、长会话里再问事实问题也会重新调工具。

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
| 可拖动双栏 | `el-splitter`,默认约 80% 城市区 / 20% AI 区 |

**两条硬约束**(§36/§37):第三方 API 没有的数据一律 `null` → 前端显示"暂无信息",**绝不让 LLM 编造餐厅价格/评分/地址/电话**;图片只用网络 URL,服务器不下载、不落盘。

> 前端超时注意:`/food/featured`(DeepSeek + 每种美食一次高德)与 `/conversations/{id}/messages`(最多 5 轮 Tool Loop)
> 实测分别可达 20 秒与 33 秒,远超 `http.js` 默认的 15 秒,因此这两个请求单独把 axios 超时放宽到 90s / 120s。
> 否则表现为"页面加载不出来,但后端日志里根本没有请求"。

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

v0.3.1 后共 **79 个测试**(v0.3 的 54 + 国际化 25)。DeepSeek 与高德全部 mock,不消耗真实 API quota。

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
| GET | `/conversations` | 是 | 当前用户的会话列表(updated_at DESC) |
| POST | `/conversations` | 是 | 新建会话,body `{"cities":[...]}`,允许空数组 |
| GET | `/conversations/{id}` | 是 | 会话详情(非本人 → 404) |
| PUT | `/conversations/{id}/cities` | 是 | 整组替换会话城市(按 adcode 去重) |
| GET | `/conversations/{id}/messages` | 是 | 会话历史消息(仅 user/assistant) |
| POST | `/conversations/{id}/messages` | 是 | 发消息 → `{user_message, assistant_message, activities[]}` |
| GET | `/health` | 否 | 健康检查 |

**v0.3.1 国际化约定**:所有接口都接受 `Accept-Language: zh-CN | en-US`(默认 `zh-CN`),
`POST /conversations/{id}/messages` 还可显式传 body `locale`(优先级最高)。
响应在保留原有中文字段的前提下**追加**双语字段与机器可读 code:
`name_en`/`address_en`/`tags_en` + `*_source`、`weather_code`、`clothing_advice_codes`、`activities[].code`/`params`、
以及错误体的 `error_code`。老客户端不带该头时行为与 v0.3 完全一致。

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

**为 v0.4 做的架构准备**:v0.3 的 Agent **不能推翻**,只能扩展 ——
新增 Retrieval Tool / RetrievalService 挂到 AgentService 下(现有 4 个 Tool 不动),
Conversation 主结构与数据库不需要重写;前端主要增加"知识来源 / 引用展示"。

后续版本增量落点:

```
v0.4  retrieval / rag  → LangChain + Milvus Lite,作为第 5 个 Tool 接入现有 AgentService
```

---

## 8. 安全

- 密码只存 bcrypt 哈希(`$2b$12$...`);
- `JWT_SECRET`、MySQL 密码、`AMAP_API_KEY`、`DEEPSEEK_API_KEY` 只存在于 `.env`,
  `.env` 已被 `.gitignore` 忽略;`.env.example` 里全是 `change_me` 占位符;
- **前端绝不持有任何第三方 Key**,高德与 DeepSeek 只由后端调用;
- 数据库异常统一降级为 `500 {"detail":"服务器暂时不可用"}`,外部 API 失败降级为 `502` + 中文提示,
  不向前端暴露 traceback / SQLAlchemyError / Key / 完整 URL。

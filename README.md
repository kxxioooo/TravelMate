# TravelMate AI — v0.3.2

**v0.1 骨架**:账户系统 + 用户偏好 + 基础 Web Shell + 本地城市搜索 + MySQL 持久化。
**v0.2 城市旅游信息**:城市搜索历史 + 高德实时天气/穿衣建议 + 景点 + 美食 + 可拖动双栏布局。
**v0.3 完整 AI Travel Agent**:DeepSeek Chat + 多 Conversation + 多城市 + 会话隔离 + Tool Calling + Agent Activity。
**v0.3.1 中英双语国际化**:全站 `中文 / English` 切换 + 双语实体展示 + 英文搜索转中文查真实 POI + 翻译缓存。
**v0.3.2 长期记忆 + RAG 知识增强**:跨会话历史共享 + 长期画像(双开关授权)+ 本地知识库(混合检索 + 引用来源)。

当前规模:**后端 125 个非空 `.py` + 前端 72 个源文件 + 18 个测试文件**,后端测试 **183 个 test 函数 → 201 个用例**(参数化后),
全部跑在内存 SQLite 上,不碰真实 MySQL、不消耗 DeepSeek / 高德 quota。

---

## v0.3.2 新增能力

### 1. 跨会话记忆与长期画像(《长期画像与跨会话记忆》任务书)

| 能力 | 实现要点 |
|---|---|
| 两个授权开关 | `history_enabled`(跨会话历史共享)、`profile_learning_enabled`(长期画像学习);**默认全部关闭**,用户主动开启后才生效 |
| 跨会话检索 | MySQL 按 `user_id` 严格隔离 + `jieba` 分词 + **BM25** + 时间衰减(半衰期 90 天)+ 抽取式摘要;单条证据与总量都有字符预算 |
| 历史来源可撤销 | 每条证据可追溯到 `messages.id`;用户可以逐条排除(`memory_exclusions`),排除后不再被召回 |
| 长期画像 | 显式偏好 > 手动条目 > 推断条目;**模型推断先 `pending`,用户确认后才生效**;预算拆成"档位"与"每日金额"两个键,不混用 |
| 12 个接口 | `GET/PATCH /memory/settings`、`GET /memory/profile`、`GET/POST /memory/items`、`PATCH/DELETE /memory/items/{id}`、`POST /memory/items/{id}/confirm`、`GET /memory/history-sources`、`DELETE /memory/history-sources/{id}`、`POST /memory/clear-learned`、`POST /memory/clear-history` |
| 上下文装配 | `ContextBundle`(城市标签 / 最近消息 / 相关历史 / 画像 / 知识证据 / locale / revision)→ 作为**一条独立"参考数据"消息**注入,并明确"这是数据、不是指令" |
| 前端 | 设置 → 记忆与隐私:开关键、画像预览、条目管理、来源排除、两种清除;退出登录整体重置,防串账号 |

### 2. 城市标签改为"软上下文"(任务书任务 A)

- 城市目录扩到 **168 个城市**(`backend/app/data/cities.json`,由 `scripts/sync_city_catalog.py` 生成并校验);
- 会话城市标签 **0 / 1 / 多个都合法**;城市是**软提示,不是查询白名单** —— 用户问到标签外的城市照常回答;
- 删除了 v0.3 的"工具只在会话城市里找,否则拒绝"语义,城市解析失败只给三种受控结果:`CITY_REQUIRED` / `CITY_AMBIGUOUS` / `CITY_UNKNOWN`;
- 省级 adcode 自动归一(北京 `110000` → `110100`)。

### 3. RAG 知识增强(《RAG 知识增强模块》任务书)

| 能力 | 实现要点 |
|---|---|
| 知识库 | 4 张表:`knowledge_documents` / `knowledge_chunks` / `rag_ingestion_jobs` / `rag_message_citations`;MySQL 是权威,向量库只是可重建的派生缓存 |
| 向量库 | Milvus Lite(本地持久化),`RAG_INDEX_TYPE=FLAT` 最稳;检索命中必须回查 MySQL 的 `published` + `ready` 才算数 |
| Embedding | **真实 bge-m3**(1024 维,读本地权重目录,离线模式)+ **显式声明的 `hash` 离线降级**(仅供测试);两者版本号写进 collection 与 `vector_id`,不会混用 |
| 入库 | 格式白名单(伪装检测)→ 清洗去重 → 按标题切分(字符单位)→ staging → embedding → 向量 upsert → 回查校验 → 发布;**任一步失败都不标 `published`** |
| 混合检索 | dense(向量)∥ sparse(BM25)→ **RRF(k=60)** 融合 → 城市软加权 → 去重 → 来源多样性截断;dense 挂掉自动降级 BM25 并标 `partial` |
| 引用 | `[1] [2] …` 编号与来源严格一一对应;非法编号从正文剥离;引用落库,刷新历史可复原;前端卡片只对 `https:` 显示原文链接 |
| 工具 | 第 5 个工具 `search_travel_knowledge`(参数 `query`/`city_name`/`need_latest`);每轮检索次数上限 + 同参复用;RAG 关闭时返回受控拒绝 |
| 联网 | 适配层完整(默认 `WEB_SEARCH_PROVIDER=none`);**无 Key 时明确返回"联网未启用",不伪造"我刚查到"** |
| 降级 | `RAG_ENABLED=false` 时不检索、不注入证据、不加载 torch/Milvus,聊天与记忆完全不受影响 |

### 4. 知识库资料导入(按《知识库资料导入指南》)

- 10 篇景点知识卡片导入 `backend/app/data/knowledge_sources/`;
- **`approved` 闸门**:`manifest.json` 里 `approved !== true` 的资料**一行都不入库**(实测 10/10 被拦),只有人工审核通过才发布;
- 审核过程与逐篇结论记录在 [`docs/知识库审核记录.md`](docs/知识库审核记录.md);
- `scripts/rag_ingest.py`(入库 CLI,支持 `--dry-run`)+ `scripts/rag_smoke_test.py`(检索冒烟,查不到就退出码 1)。

### 5. Alembic 迁移

```
0001_baseline           引入记忆/RAG 之前的 7 张表
0002_memory             5 张记忆表 + messages 检索索引
0003_rag_knowledge      3 张知识表
0004_rag_citations      1 张引用表
0005_document_generation 文档生成 2 张表(v0.3.3 进行中)
```

**新库从零 `alembic upgrade head` 建出的结构与 ORM 完全一致(逐表逐列比对,6/6 通过),`downgrade base` 干净回滚**;
已在跑的开发库用 `alembic stamp` 标记版本(不执行 DDL),不会动既有数据。

### 6. 进行中:v0.3.3 AI Agent 文档生成

《AI Agent 旅游攻略 Word / PowerPoint 生成模块》已开工:行程数据契约(`schemas/documents.py`)、
文档模块契约(`services/documents/contracts.py`)、两张表 + 迁移已完成;
渲染器 / 生成编排 / 工具 / API / 前端卡片在后续版本补齐。

> 规模:后端 125 个非空 `.py` + 前端 72 个源文件 + 18 个测试文件;后端测试 **201 passed**。

---

## v0.3.1 能力(中英双语)

| 能力 | 实现要点 |
|---|---|
| 语言切换 | 顶部右侧 `中文 \| English`(未登录页固定在右上角);**即时切换、刷新保持、不重置**当前城市 / Tab / Splitter / 会话 / 消息 |
| 全站文案 i18n | `vue-i18n` + `el-config-provider`;**zh-CN 与 en-US 的 key 完全一致**(351/351);英文模式零未授权中文 |
| 城市双语 | 168 个城市补齐 `city_name_en` / `province_en` / `pinyin_initials` / `aliases_en`;中英文、拼音、首字母、异写都能搜到同一城市,展示为 `Chengdu (成都)` |
| 英文搜索真查高德 | `ancient town` → 词典/翻译解析成 `古镇` → 用**中文关键词 + 原 `types`** 查高德;查不到就返回受控 422 `query.unrecognized`,**绝不悄悄退回默认 Top10** |
| POI 双语 | 名称/地址/标签带 `*_en` 与 `*_source`(`verified`/`model`/`transliterated`/`fallback`);`poi_id`、经纬度、评分、价格、电话、图片**永不被翻译或改写** |
| 翻译缓存 | MySQL `entity_translations`,`UNIQUE(provider, entity_key, field_name, target_locale, source_hash, translation_version)`;原文变则 hash 变、自动失效 |
| 天气/穿衣 codes | 后端返回 `weather_code` 与 `clothing_advice_codes`(枚举),前端按语言渲染;数字原值不动 |
| Activity codes | `code` + `params`(如 `agent.weather_found` + `{city_name}`),前端按语言渲染;`text` 保留做兼容 |
| Agent 按语言生成 | 中/英分别组系统提示词;英文回答自然英文,专有名词用 `English (中文)`;**历史消息永不改写** |

**两条红线**:①拿不到可信英文名时明确降级(`fallback`),**不编造官方译名**;②`poi_id` / `adcode` / `conversation_id` / Tool 名等业务标识**不本地化**。

---

## v0.3 能力(完整 AI Travel Agent)

| 能力 | 实现要点 |
|---|---|
| 真实 AI Chat | `ChatPanel` 取代 `AiPlaceholder`;**未选城市时 Chat 占主页主要区域**,选中城市后才切到 80/20 Splitter |
| 多 Conversation | 数量无业务限制;数据库 `conversations` + `conversation_cities`(0 / 1 / 多城市均可),可随时改当前会话城市 |
| Conversation Drawer | **只存在于 AI 区内部**且默认隐藏;网站 Sidebar **始终不出现**对话历史 |
| 会话记忆规则 | Preferences **跨会话共享**(通过 Tool 读取);Message History **严格按 `conversation_id` 隔离** |
| Agent Tool Calling | 基础 4 个工具:`get_user_preferences` / `get_weather` / `search_attractions` / `search_food`,**全部复用 v0.2 的 service,不重写业务逻辑**;v0.3.2 追加第 5 个 `search_travel_knowledge` |
| Agent Activity | 只显示**实际执行过**的工具(✓/●/!),不显示 Chain-of-Thought,不伪造未发生的调用 |
| 消息持久化 | 数据库只存最终 `user` / `assistant`;Agent 内部的 tool-call / tool 消息**只在单次请求内传递,不落库** |
| Recommended Prompts | 点击后填入 ChatInput,**不自动发送**;没有 active 会话时首次发送会自动创建一个 `cities=[]` 的会话 |

**Agent 行为红线**:`user_id` 只能来自服务端,模型的工具 Schema 里没有它;dispatcher 白名单派发,禁止 `eval`;
工具没返回的价格/评分/地址/电话一律"暂无信息",**绝不让模型编造**;整体失败时**不写虚假的 assistant 成功消息**。

---

## v0.2 能力(城市旅游信息)

| 能力 | 实现要点 |
|---|---|
| 城市搜索历史 | `city_view_history` 表,`UNIQUE(user_id, adcode)` → 重复选同城只更新 `viewed_at`,不产生重复 |
| Recent Searches | 搜索框聚焦且无关键词时,下拉显示最近 10 个城市的本地历史 |
| 实时天气 + 穿衣建议 | 高德天气**请求两次**(`base` 拿实时、`all` 拿预报)后合并;穿衣建议按温度阈值 + 天气文本(含"雨"补雨具)在本地生成,不调用 DeepSeek |
| 景点 Tab(默认) | 默认 10 个用高德**类别码 `types=110000`** 取(不能按关键词"景点",否则会混进写字楼);关键词搜索切到 `page_size=20` 并支持 Load More |
| 美食 Tab + 搜索 | DeepSeek 生成 10 种代表美食(JSON),再对每种查高德餐饮 POI 取 2 家真实餐厅;关键词搜索切餐厅结果模式 |
| 可拖动双栏 | `el-splitter`,默认约 80% 城市区 / 20% AI 区 |

**两条硬约束**:第三方 API 没有的数据一律 `null` → 前端显示"暂无信息",**绝不让 LLM 编造餐厅价格/评分/地址/电话**;
图片只用网络 URL,服务器不下载、不落盘。

> 前端超时注意:`/food/featured` 与 `/conversations/{id}/messages`(最多 5 轮 Tool Loop)实测可达 20 / 33 秒,
> 因此这两个请求单独把 axios 超时放宽到 90s / 120s。否则表现为"页面加载不出来,但后端日志里根本没有请求"。

---

## 0. 快速启动

本机依赖与数据库都已就绪,只需**两个窗口**(保持窗口开着即为运行中,Ctrl+C 停止):

```
start-backend.cmd      → 后端 http://127.0.0.1:8000   (接口文档 /docs)
start-frontend.cmd     → 前端 http://localhost:5173
```

双击即可;也可以在任意终端里执行。`.cmd` 只是启动器,真正的逻辑在配套的 `.ps1` 里
(用 `-ExecutionPolicy Bypass` 绕开"系统禁止运行脚本"的默认策略)。

**本机环境注意事项**

- 系统 PATH 里**没有 `node`**。`start-frontend.ps1` 会自动回退到 DSH 桌面端内置的 Node + pnpm。
- `backend\.venv` 里的依赖已装好。RAG 相关依赖(向量库 / torch / FlagEmbedding)单独放在
  `requirements-rag.txt` —— 不跑 RAG 的环境不必安装。
- MySQL80 服务是"自动"启动类型,开机即在运行;`travelmate` 库与账号已建好,密码写在 `.env`。

---

## 1. 环境要求

| 组件 | 版本 |
|---|---|
| Node.js | ≥ 20(vite 8 要求) |
| Python | ≥ 3.11(开发使用 3.13) |
| MySQL | 8.0 |

RAG 可选依赖:`pymilvus` + `milvus-lite`、`langchain-text-splitters`、`pypdf`、`python-docx`、
`torch`、`transformers`、`sentence-transformers`、`FlagEmbedding`(见 `backend/requirements-rag.txt`)。

---

## 2. 后端启动

```bash
cd backend

# 1) 虚拟环境 + 依赖
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
pip install -r requirements-rag.txt   # 需要 RAG 时

# 2) 建库建用户(用有权限的账号执行一次)
#    CREATE DATABASE travelmate CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
#    CREATE USER 'travelmate'@'localhost' IDENTIFIED BY '你的密码';
#    GRANT ALL PRIVILEGES ON travelmate.* TO 'travelmate'@'localhost';

# 3) 配置
copy ..\.env.example ..\.env    # 然后填 MYSQL_PASSWORD 与 JWT_SECRET

# 4) 建表(二选一)
python -m alembic upgrade head  # 推荐:新库直接建到最新版本
python -m app.db.init_db        # 或:按 ORM 建表(本地开发够用)

# 5) 启动
python -m uvicorn app.main:create_app --factory --reload --port 8000
```

`create_app` 用工厂模式暴露,导入模块不会连数据库;`init_db()` 只在真正构造应用时执行。

自检:

```bash
curl http://127.0.0.1:8000/health      # {"status":"ok"}
```

### 2.1 导入知识库(需要 RAG 时)

```bash
cd backend
python scripts/rag_ingest.py --manifest app/data/knowledge_sources/manifest.json --dry-run
python scripts/rag_ingest.py --manifest app/data/knowledge_sources/manifest.json
python scripts/rag_smoke_test.py --query "成都武侯祠历史"     # 查不到会返回退出码 1
```

**审核闸门**:`manifest.json` 里 `approved` 不是 `true` 的资料会被跳过(`SKIP(not_approved)`),
不会写库、不会生成向量。未审核资料不得自动发布。

### 2.2 迁移

```bash
cd backend
python -m alembic current       # 当前版本
python -m alembic upgrade head  # 升级到最新
python -m alembic downgrade -1  # 回退一步(会删数据,先备份)
```

已在运行的旧库如果不希望重新建表,先用 `python -m alembic stamp <revision>` 标记基线,再 `upgrade head`。

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
所以浏览器眼里只有 5173 一个源,HttpOnly Cookie 能正常携带。

---

## 4. 测试

```bash
cd backend
python -m pytest tests -q                  # 全部
python -m pytest tests/test_rag_*.py -q     # 只跑 RAG
```

**201 个用例全部通过**,DeepSeek / 高德 / 联网搜索全部 mock 或关闭,不消耗真实 API quota。
RAG 用例用临时 Milvus 文件 + `hash` 离线 embedding,不需要下载模型。

---

## 5. 认证方案

```
JWT(HS256) → HttpOnly Cookie
Cookie: HttpOnly=true, SameSite=Lax, Secure=(APP_ENV=="production")
前端 Axios: withCredentials=true,永远不读 JWT
```

## 6. API

统一前缀 `/api/v1`。

### 6.1 账户 / 偏好 / 城市 / 旅游信息

| Method | Path | 登录 | 功能 |
|---|---|:--:|---|
| POST | `/auth/register` | 否 | 注册(同时建立登录态) |
| POST | `/auth/login` | 否 | 登录 |
| POST | `/auth/logout` | 是 | 退出(清 Cookie) |
| GET | `/auth/me` | 是 | 当前用户(刷新恢复登录态) |
| GET/PUT | `/preferences/me` | 是 | 读取 / 保存偏好(保存即置 `onboarding_completed`) |
| POST | `/preferences/skip` | 是 | 跳过 Onboarding(不伪造偏好) |
| GET/POST | `/cities/history` | 是 | 最近搜索城市 / 记录一次浏览(同城 upsert) |
| GET | `/weather?adcode=` | 是 | 实时天气 + 预报合并 + 穿衣建议 |
| GET | `/attractions`、`/attractions/{poi_id}` | 是 | 景点列表(分页/关键词)/ 详情 |
| GET | `/food/featured`、`/food/restaurants`、`/food/restaurants/{poi_id}` | 是 | 代表美食 + 真实餐厅 / 搜索 / 详情 |

### 6.2 会话与聊天

| Method | Path | 登录 | 功能 |
|---|---|:--:|---|
| GET/POST | `/conversations` | 是 | 会话列表 / 新建(允许 `cities=[]`) |
| GET | `/conversations/{id}` | 是 | 会话详情(非本人 → 404) |
| PUT | `/conversations/{id}/cities` | 是 | 整组替换会话城市(按 adcode 去重) |
| GET | `/conversations/{id}/messages` | 是 | 会话历史消息(仅 user/assistant) |
| POST | `/conversations/{id}/messages` | 是 | 发消息 → `{user_message, assistant_message, activities[], citations[]}` |

### 6.3 记忆与画像(v0.3.2)

| Method | Path | 功能 |
|---|---|---|
| GET/PATCH | `/memory/settings` | 两个授权开关 + 记忆用量 |
| GET | `/memory/profile` | 画像摘要 + 结构化画像 |
| GET/POST | `/memory/items` | 记忆条目列表 / 手动新增 |
| PATCH/DELETE | `/memory/items/{id}` | 修改 / 删除(删除同时写排除) |
| POST | `/memory/items/{id}/confirm` | 确认一条 `pending` 推断项 |
| GET/DELETE | `/memory/history-sources`、`/memory/history-sources/{message_id}` | 历史来源列表 / 排除某条来源 |
| POST | `/memory/clear-learned`、`/memory/clear-history` | 清除学习到的画像 / 清除历史记忆 |

### 6.4 知识库(v0.3.2)

| Method | Path | 功能 |
|---|---|---|
| GET | `/rag/status` | 是否启用、索引是否就绪、文档/片段数(不含路径与 Key) |
| POST | `/rag/search` | 显式检索(`query` 2~500、`top_k` 1~10),关闭时返回 `disabled` |
| GET | `/rag/citations/{message_id}` | 某条 assistant 消息保存的引用(非本人统一 404) |

> `/rag/admin/*` **刻意没有注册**:当前用户模型没有管理员角色,把"登录=管理员"当权限会越权,
> 资料导入统一走服务器 CLI。

**国际化约定**:所有接口接受 `Accept-Language: zh-CN | en-US`(默认 `zh-CN`),
`POST /conversations/{id}/messages` 还可显式传 body `locale`(优先级最高)。
响应在保留原有中文字段的前提下**追加**双语字段与机器可读 code。

外部 API 备注:高德个人 Key 有 **QPS 限制**,连续快速请求会返回 `status=0`(看起来像"无数据");
`amap_client` 已内置退避重试,`food/featured` 的 10 路查询用 `Semaphore(3)` + 间隔控流。

---

## 7. 分层约定

```
frontend/src  router / api / stores / views / components / i18n / constants / utils / data / styles
backend/app   api(router, deps, routes) / services(memory, rag, documents) / schemas / models / db / core
backend       migrations(Alembic) / scripts(CLI) / tests / app/data(城市目录, 知识库资料)
```

- 路由只负责 HTTP 语义,业务逻辑在 `services`;
- 偏好选项只在 `constants/preferences.js` 定义一次;
- 城市索引只在 `data/cities.json`(后端)与 `data/cities.js`(前端)各一份,由 `scripts/sync_city_catalog.py` 保证一致;
- 城市上下文只有 `stores/city.js` 的 `openCity()` 一个入口;
- 缺失值统一走 `utils/display.js`,不在各组件里各写一套兜底;
- **记忆只有一套**:RAG 的 `memory_adapter` 只适配既有的 `services/memory`,不另建第二套画像/历史。

### 七个不可回退的约束

1. 城市标签是**软上下文**,不是白名单;
2. 记忆两个开关**默认关闭**,关闭时绝不召回;
3. 知识库只发布 `approved=true` 且通过了 `published` + `ready` 校验的内容;
4. 检索必须回查 MySQL 才算数;向量库可整库删除重建;
5. 引用 `[n]` 与来源严格一一对应,编造的编号会被剥离;
6. 模型不能传 `user_id`、文件路径或下载 URL;
7. 没有真实结果时就如实说"没查到",不编造来源、链接或文件。

---

## 8. 安全

- 密码只存 bcrypt 哈希(`$2b$12$...`);
- `JWT_SECRET`、MySQL 密码、`AMAP_API_KEY`、`DEEPSEEK_API_KEY`、`TAVILY_API_KEY` 只存在于 `.env`,
  `.env` 已被 `.gitignore` 忽略;`.env.example` 里全是 `change_me` 占位符;
- **前端绝不持有任何第三方 Key**,高德 / DeepSeek / 联网搜索只由后端调用;
- 记忆与知识库的所有查询都带 `user_id` 条件;非本人资源统一 404;
- 知识库入库路径只允许在 `app/data/seed_knowledge` 与 `app/data/knowledge_sources` 之内;
- 联网抓取只允许 `https` + 公网地址(DNS 逐 IP 复查、重定向逐跳复查、拒绝内网/元数据/带凭证 URL);
- 数据库异常统一降级为 `500 {"detail":"服务器暂时不可用"}`,外部 API 失败降级为 `502` + 中文提示,
  不向前端暴露 traceback / SQLAlchemyError / Key / 完整 URL;
- 向量库目录(`app/data/rag_state/`)是派生缓存,已被 `.gitignore` 忽略。

---

## 9. 相关文档

| 文件 | 内容 |
|---|---|
| [`docs/验收矩阵_V0.3.2.md`](docs/验收矩阵_V0.3.2.md) | 两份任务书逐条验收结果(通过 / 未实测 / 刻意不做),含浏览器端截图 |
| [`docs/知识库审核记录.md`](docs/知识库审核记录.md) | 10 篇景点资料的逐篇审核结论、许可义务与人工复核清单 |
| `backend/app/data/knowledge_sources/README_IMPORT.md` | 资料包自带说明(来源、许可、审核要求) |

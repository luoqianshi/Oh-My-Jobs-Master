# Job-Master 个人秋招工作台 · 实施计划

## 一、摘要

构建一个 **单 HTML 主导的轻量 Agentic 秋招工作台**：左侧可折叠/可拖宽的导航栏 + 右侧内容区，数据以浏览器 localStorage 为运行时状态、以项目内 `data/` 目录的 CSV/JSON 文件为持久化真相（File System Access API 自动双向同步），核心能力沉淀为 `.trae/skills/` 中的 SKILL，在 TraeCode 中由 Agent 驱动（自动提取邮箱新邮件、按截图/链接自动新增投递记录、语音式查询与修改进度）。

已确认的关键决策：
- 邮箱接入：**IMAP 授权码直连**（本地 Python 脚本拉取，Agent 筛选解析）
- 数据同步：**File System Access API 自动同步**（授权 `data/` 目录，Agent 与浏览器共用同一份数据文件）
- SKILL 位置：**项目内 `.trae/skills/`**

## 二、现状分析

- 工作目录当前为**空目录**，无任何代码、无 git 仓库、无 `.trae` 配置，属于从零搭建。
- 运行环境：Windows，本地直接双击打开 `index.html` 使用（file:// 协议，Chromium 下属于安全上下文，File System Access API 可用）。
- 用户偏好（来自用户画像）：Gradio 风格极简浅色主题，白/浅灰背景，**Emerald 绿 #10B981** 主色，SVG 图标（stroke-width=1.5），无霓虹/玻璃拟态/脉冲动画，表单分组布局、简洁表格优先。
- 技术栈：纯原生 HTML/CSS/JS 单文件，零构建、零运行时依赖；Python 3 标准库（邮箱脚本，零第三方依赖）。

## 三、总体架构

### 3.1 目录结构（最终形态）

```
2026小骆的个人秋招工作台/
├── index.html                          # 单文件主应用（全部 CSS/JS 内联）
├── data/
│   ├── jobmaster_data.csv              # 投递记录主数据（浏览器↔Agent 共享真相）
│   └── emails.json                     # 邮箱原始邮件池（脚本写入，Agent 消费）
├── scripts/
│   └── fetch_emails.py                 # IMAP 拉取网易邮箱新邮件（Python 标准库）
├── config/
│   ├── secrets.example.json            # 邮箱授权码配置模板
│   └── secrets.local.json              # 实际授权码（用户创建，含敏感信息）
└── .trae/
    ├── rules/project_rules.md          # 项目规则：数据模型、文件职责、Agent 行为约束
    └── skills/
        ├── jobmaster-sync-emails/SKILL.md   # 每日提取新邮件并更新进度
        ├── jobmaster-add-entry/SKILL.md     # 从截图/官网链接/文字描述新增投递
        └── jobmaster-manage/SKILL.md        # 查询/修改/删除/统计进度
```

### 3.2 数据流

```
┌─────────────┐  File System Access API   ┌──────────────────┐
│  index.html  │ ◄──── 授权 data/ 目录 ───► │  data/*.csv|json  │
│ (localStorage│      变更即写回/焦点即读取   │                  │
│  为运行时态)  │                            └────────┬─────────┘
└─────────────┘                                     │ 直接读写
                                                    ▼
┌─────────────┐   运行脚本/读图/写CSV    ┌──────────────────┐
│ Trae Agent   │ ◄──── SKILL 编排 ────── │  .trae/skills/*  │
└─────────────┘                         └──────────────────┘
        │
        ▼ python scripts/fetch_emails.py（IMAP 授权码）
┌─────────────┐
│ 网易邮箱 IMAP │
└─────────────┘
```

**分工原则**：脚本只负责"采集"（拉邮件到 emails.json），Agent 负责"理解"（判断是否秋招邮件、匹配公司、决定状态变更），SKILL 负责"编排"（把流程固化成可触发的能力），浏览器负责"呈现与手工维护"。

## 四、数据模型（决策完整定义）

### 4.1 `data/jobmaster_data.csv` 列定义

| 列名 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一 ID：`jm_` + 13位时间戳 + `_` + 4位随机hex，如 `jm_1760000000123_a1b2`（Agent 新增时按同规则生成） |
| `type` | enum | 所属类型：`互联网` / `央国企` |
| `company` | string | 企业名称 |
| `department` | string | 所属部门（可空） |
| `position` | string | 投递岗位 |
| `appliedAt` | date | 投递时间 `YYYY-MM-DD` |
| `status` | enum | 当前进度（见 4.2） |
| `link` | string | 官网/招聘页链接（可空） |
| `source` | enum | 来源：`手动创建` / `邮箱提取` / `截图识别` |
| `notes` | string | 备注，状态变更时追加 `MM-DD 状态（来源）` 短记录，`\n` 分隔 |
| `createdAt` | datetime | `YYYY-MM-DD HH:mm` |
| `updatedAt` | datetime | `YYYY-MM-DD HH:mm`，行级合并依据 |

**格式规范**：UTF-8 **带 BOM**（Excel 直开不乱码），标准 CSV 转义（逗号/引号/换行），表头固定不可变，写入为全量覆盖。

### 4.2 进度状态枚举（同时是看板列顺序）

`简历筛 → 笔试筛 → 专业面 → 主管面 → HR面 → Offer`

附加终止态：`已挂`（灰色第 7 列，用于记录被拒的投递，保持看板不积压。如不需要可在评审时去掉）。

### 4.3 `data/emails.json` 结构

```json
{
  "lastFetchedAt": "2026-09-15T10:30:00",
  "emails": [
    {
      "id": "em_1760000000123_c3d4",
      "messageId": "<abc@163.com>",
      "from": "hr@careers.example.com",
      "fromName": "腾讯招聘",
      "subject": "【腾讯】面试邀请函",
      "date": "2026-09-15T09:00:00",
      "snippet": "正文前300字",
      "processed": false,
      "matchedEntryId": null,
      "matchedAction": null
    }
  ]
}
```

`messageId` 用于去重；`processed/matchedEntryId/matchedAction` 由 Agent 处理后回写。

### 4.4 同步与合并策略

- 首次使用：页面引导点击"启用数据同步"→ `showDirectoryPicker()` 选择 `data/` 目录 → directory handle 存入 IndexedDB → 之后免授权（`queryPermission` 通过即静默读写）。
- **写**：任何数据变更 → 先写 localStorage（即时）→ 再写 CSV（防抖 500ms）。
- **读/合并**：页面加载、`window focus`（防抖 800ms）、每 60s 定时——比较 CSV `lastModified` 与内存 `lastSyncedAt`，若外部（Agent）改过 → 重读 CSV，与 localStorage **按行合并：`updatedAt` 新者胜**，删除以行是否存在为准（CSV 为准）。
- 兜底：数据管理页保留"手动导出 CSV / 手动导入 CSV"按钮；未授权目录时应用仍可纯 localStorage 运行。
- 仅支持 Chromium（Chrome/Edge）；其他浏览器自动降级为手动模式并提示。

## 五、变更清单（逐文件 what/why/how）

### 5.1 `data/jobmaster_data.csv`（新建）
- **what**：仅表头一行的空 CSV（UTF-8 BOM，列见 4.1）。
- **why**：数据真相文件必须先于应用与 SKILL 存在；Agent 和浏览器都读写它。
- **how**：直接写入 12 列表头。

### 5.2 `data/emails.json`（新建）
- **what**：`{"lastFetchedAt": null, "emails": []}`。
- **why**：邮箱脚本与 Agent 之间的邮件池。

### 5.3 `index.html`（新建，核心工作量）

**布局**：
- 左侧边栏（默认宽 220px，拖拽手柄可调 180–320px，顶部按钮可整体折叠为 56px 图标条）：Logo/标题 `Job-Master`、SVG 导航项（投递列表、进度看板、邮箱收件、数据管理）、底部固定同步状态指示灯（绿=已同步 / 黄=未授权 / 红=错误）。
- 右侧内容区：模块标题 + 操作栏 + 内容。

**UI 规范**：背景 `#F9FAFB`，面板 `#FFFFFF`，边框 `#E5E7EB`，主色 `#10B981`（hover `#059669`），文字 `#111827`/次级 `#6B7280`；系统字体栈；SVG 图标 stroke-width=1.5（Feather 风格，内联）；无动画装饰（仅 150ms hover 过渡）；桌面优先（≥1024px），窄屏表格横向滚动。

**模块 1：投递列表**
- 工具栏：关键词搜索（公司/岗位模糊）、类型筛选、状态筛选、`+ 新增投递` 按钮。
- 表格列：类型 / 企业 / 部门 / 岗位 / 投递时间 / 状态（行内下拉即改）/ 链接（SVG 外链图标）/ 备注 / 操作（编辑、删除）。
- 新增/编辑用模态框表单（Gradio 式分组），删除需确认。
- 默认按投递时间倒序；数据量按 ≤500 行直渲设计，不分页。

**模块 2：进度看板**
- 7 列（4.2 枚举），列头显示名称+计数，`已挂` 列灰化。
- 卡片：企业 + 岗位 + 投递日期 + 类型徽标（互联网绿/央国企蓝描边）。
- HTML5 Drag & Drop 拖拽换列即改 `status` 并触发同步写盘；点击卡片打开编辑模态框。

**模块 3：邮箱收件**
- 读取 `data/emails.json` 渲染邮件列表：日期 / 发件人 / 主题 / 匹配结果（已关联的投递记录名 + 处理动作）。
- 未匹配邮件提供「一键创建投递」按钮（预填企业名，状态=简历筛，来源=邮箱提取）。
- 未启用目录同步时显示引导提示。

**模块 4：数据管理**
- 同步状态卡：授权状态、目录名、最近读/写时间、「启用数据同步」「立即重新同步」按钮。
- 手动导出/导入 CSV（`<input type=file>` + 下载，作为降级通道）。
- 统计卡：总投递数、本周新增、各状态计数、Offer 数。
- 危险操作：清空本地缓存（保留 CSV）。

### 5.4 `scripts/fetch_emails.py`（新建）
- **what**：零依赖 Python 3 标准库 IMAP 客户端。
- **how**：
  - 读取 `config/secrets.local.json`：`{"imap_host": "imap.163.com", "email": "...", "auth_code": "..."}`（163/126/yeah 仅 host 不同）。
  - `imaplib.IMAP4_SSL(host, 993)` + `login(email, auth_code)`；`search(None, 'SINCE', since)`；解析 `From/Subject/Date` 头 + 正文前 300 字（`email` 标准库，处理 GBK/UTF-8 编码与 base64 主题）。
  - 以 `messageId` 去重后追加进 `data/emails.json`，更新 `lastFetchedAt`。
  - CLI：`python scripts/fetch_emails.py --since 2026-09-15 [--config path] [--data-dir path]`；`--since` 缺省取当天。
  - 只采集不过滤（是否秋招邮件由 Agent 判断）；输出本次新增条数摘要。
- **注意**：NetEase 需在网页版邮箱设置中开启 IMAP 服务并生成"客户端授权码"（非登录密码）。

### 5.5 `config/secrets.example.json`（新建）
授权码配置模板，含注释性字段说明；`secrets.local.json` 由用户参照创建。

### 5.6 `.trae/rules/project_rules.md`（新建）
写给 Agent 的项目规则：数据模型全量定义（4.1–4.3 的枚举/ID 规则/CSV 格式）、各文件职责、"任何数据修改必须全量读→改→写回 CSV 且不破坏表头/转义"、邮箱流程分工、敏感文件 `secrets.local.json` 不得外泄内容。

### 5.7 三个 SKILL（新建 `.trae/skills/<name>/SKILL.md`）

**jobmaster-sync-emails**（触发词：提取邮件/同步邮箱/今天的邮件）
1. 读 `data/emails.json` 取 `lastFetchedAt` 决定 `--since`；运行 `python scripts/fetch_emails.py`（首次先 `python --version` 检查环境）。
2. 读新增邮件 + 读 `data/jobmaster_data.csv` 企业列表。
3. 筛选秋招相关邮件：发件人/主题与企业名模糊匹配（剥离"招聘/校招/HR"等后缀），主题关键词分类（笔试/测评→笔试筛；面试邀请→对应轮次；offer→Offer；简历评估→简历筛）。
4. 逐封处理：已有记录→更新 `status` 并在 `notes` 追加；新公司→新增整行（来源=邮箱提取）。
5. 回写 CSV 与 emails.json（`processed/matchedEntryId/matchedAction`），向用户输出变更摘要表。

**jobmaster-add-entry**（触发：提供截图/官网链接/文字描述要求新增）
1. 截图→Read 识别；链接→WebFetch 抓取；文字→直接解析。
2. 提取 type/company/department/position/link，生成 ID 与时间戳，来源标 `截图识别` 或 `手动创建`。
3. 查重（同公司同岗位未终止的记录提示用户确认），追加写 CSV，回报新增行。

**jobmaster-manage**（触发：查询/改进度/删记录/统计）
读 CSV→执行查/改/删→全量写回→输出结果；统计类问题输出 Markdown 小表。

### 5.8 不做的事（明确边界）
- 不引入前端框架/构建工具/CDN 依赖；不做用户登录、云同步、多用户。
- 不做图表大屏、面试日历等扩展模块（架构预留：导航数组 + 模块注册函数即可插拔）。
- 邮箱脚本不做定时自动运行（由用户在 Trae 中按需触发，避免触发网易频控）。

## 六、实施顺序

1. 目录骨架 + 数据文件（5.1/5.2/5.5）
2. `index.html` 布局与导航框架（侧栏折叠/拖宽、模块路由）
3. 数据层：state + localStorage + IndexedDB handle + CSV 读写/合并（4.4 全部策略）
4. 投递列表模块（CRUD/筛选/搜索/模态框）
5. 看板模块（7 列 + 拖拽）
6. 邮箱收件模块 + 数据管理模块
7. `scripts/fetch_emails.py`
8. `.trae/rules/project_rules.md` + 三个 SKILL
9. 端到端验证（见下）

## 七、验证步骤

1. **基础 CRUD**：Edge 打开 `index.html` → 引导授权 `data/` 目录 → 新增一条投递 → 文本编辑器确认 CSV 出现该行（BOM/转义正确）→ 编辑、删除均同步。
2. **看板拖拽**：卡片从简历筛拖到笔试筛 → CSV `status/updatedAt` 更新。
3. **Agent 写入仿真**：手动在 CSV 中改一行（模拟 Agent）→ 切回浏览器标签页 → focus 触发自动合并显示。
4. **恢复能力**：清空 localStorage → 刷新 → 从 CSV 完整恢复。
5. **邮箱链路**：`python --version` 确认环境 → 配置授权码 → 运行脚本 → `emails.json` 出现新邮件且重复运行不重复采集。
6. **SKILL 链路**：在 Trae 中说"帮我提取今天的秋招邮件"→ 走完 sync-emails 全流程 → 浏览器侧看到进度更新；给一张招聘截图说"帮我加上这条"→ 验证 add-entry。
7. **降级通道**：撤销目录授权 → 手动导出/导入按钮仍可用。

## 八、风险与说明

- **IMAP 授权码**：需用户一次性在网易邮箱网页版开启 IMAP 并生成授权码；授权码是敏感信息，只存 `config/secrets.local.json`，SKILL 中约束 Agent 不得回显。
- **浏览器兼容**：自动同步仅 Chrome/Edge；已提供手动导出导入兜底。
- **合并极端情况**：同一行被浏览器与 Agent 同时修改时按 `updatedAt` 新者胜，旧方丢失（低频可接受，规则文档中说明）。
- **Python 环境**：若用户机器无 Python 3，Agent 首次运行 SKILL 时检测并引导安装，或后续按需补 Node 版脚本。

# Job-Master 项目规则（供 AI 阅读）

## 项目概述

个人秋招工作台：单 HTML 应用（index.html）+ 本地数据文件（data/）+ IMAP 采集脚本（scripts/）。
用户在浏览器中手工维护数据，同时 Trae Agent 可直接读写数据文件——双方通过 `data/` 目录共享同一份数据。数据以浏览器本地缓存（localStorage）为第一优先，变更实时写入缓存后再自动落盘（定时 60 秒 / 切走标签页 / 关闭页面前）。浏览器经 HTTP（本地/预览服务器）打开时，index.html 默认自动同步项目根目录下的 `./data`：读取（GET）始终自动合并（页面获得焦点时检测外部变更）；写回（PUT）取决于服务器，不支持时降级为只读同步，可在「数据管理」中切换为 File System Access 目录授权同步获得完整读写。侧边栏收起后点击品牌 Logo 复原。

## 文件职责

| 文件 | 职责 | 写入方 |
|---|---|---|
| `index.html` | 单文件应用（全部 UI 与逻辑，零依赖） | 修改需谨慎，不引入外部依赖 |
| `data/jobmaster_data.csv` | 投递记录主数据（唯一真相） | 浏览器与 Agent 双向读写 |
| `data/emails.json` | 邮箱原始邮件池 | fetch_emails.py 追加；Agent / 浏览器回写处理状态 |
| `scripts/fetch_emails.py` | IMAP 邮件采集（零第三方依赖，Python 3.8+） | 只采集，不做业务判断 |
| `config/secrets.local.json` | 邮箱授权码（用户创建） | 含敏感信息，绝不回显、绝不外传 |

## 数据模型

### data/jobmaster_data.csv

- 编码：UTF-8 带 BOM；换行 CRLF；标准 CSV 转义（逗号/引号/换行需加引号并双写引号）
- 写入纪律：**全量读取 → 内存中修改 → 完整覆盖写回**，表头与列顺序不可变
- 列定义：`id,company,department,status,position,industry,location,latestDate,link,source,notes,createdAt,updatedAt`
- 枚举值：
  - `status`：预设 待投递 / 简历筛 / 笔试筛 / 专业面 / 主管面 / HR面 / Offer / 已挂；**支持自定义状态——直接写入新值即可，前端会自动收入下拉列表、看板列、筛选与统计**
  - `industry`（所属行业，单选）：预设 银行 / 制造 / 车企 / 互联网 / 央企 / 证券；**支持自定义行业——直接写入新值即可，前端会自动收入下拉列表**
  - `location`（工作地点，多选）：预设 杭州 / 上海 / 广州 / 天津 / 合肥 / 北京 / 深圳 / 南京；多个以 `;` 分隔（如 `上海;北京`）；**支持自定义工作地点——直接写入新值即可，前端会自动收入多选列表**
  - `source`：手动创建 / 邮箱提取 / 截图识别
- id 规则：`jm_` + 13 位毫秒时间戳 + `_` + 4 位十六进制，如 `jm_1760000000123_a1b2`
- 时间格式：`latestDate`（最新日期）= `YYYY-MM-DD`，指与该投递最新进展相关的日期，可为未来日期（如笔试/面试安排）；`createdAt`/`updatedAt` = `YYYY-MM-DD HH:mm`
- 状态变更时：更新 `status` 与 `updatedAt`，并在 `notes` 末尾追加一行 `MM-DD 新状态`（多行以 `\n` 分隔，写入 CSV 时需转义）；`latestDate` 仅在用户明确给出新日期时更新
- 兼容：旧列 `type`→`industry`（值 `央国企`→`央企`）、`appliedAt`→`latestDate`，读到旧表头时自动映射，写回一律用新表头

### data/emails.json

结构：`{ "lastFetchedAt": "ISO时间或null", "emails": [ ... ] }`，每封邮件字段：
`id, messageId, from, fromName, subject, date, snippet, processed, matchedEntryId, matchedAction`

Agent 处理一封邮件后必须回写：`processed=true`、`matchedEntryId`（关联的投递 id，无则为 null）、`matchedAction`（如"更新进度"/"新增投递"/"ignored"）。

## Agent 行为准则

1. 修改 CSV 前先完整读取；写回时保留 UTF-8 BOM、CRLF 换行、标准转义
2. 任何写操作后，向用户报告变更摘要（改了哪些行、哪些字段）
3. 删除或多行覆盖类破坏性操作，必须先向用户确认
4. `config/secrets.local.json` 中的授权码不得在回复中回显
5. 邮箱业务判断逻辑见 `.trae/skills/jobmaster-sync-emails/SKILL.md`
6. 完成数据修改后提醒用户：浏览器中打开 index.html 即可自动看到变更

## README 更新钩子（每次 /goal 完成后自动执行）

每当一次 `/goal` 的全部任务完成并通过验证后，必须执行以下钩子步骤，视为目标完成的必要条件：

1. 检查本次变更是否影响 README.md 所描述的功能清单、数据结构、使用方式等内容；
2. 如有影响，同步更新 README.md 对应章节，并将文末「最后更新」改为当天日期；
3. 无影响也需复核一遍文末「最后更新」日期是否与本次变更日期一致；
4. 在向用户报告的变更摘要中，注明 README 是否已更新及更新了哪些章节。

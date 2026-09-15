---
name: jobmaster-sync-emails
description: 拉取网易邮箱新增邮件并自动更新秋招进度表（data/jobmaster_data.csv）。当用户说「提取邮件」「同步邮箱」「拉取今天的邮件」「看看邮件里有什么新进展」「邮箱里有没有笔试/面试通知」时使用。
---

# 同步邮箱 → 更新秋招进度

## 前置检查（每次先做）

1. `python --version`：确认 Python 3 可用；不可用则引导用户安装后重试
2. `config/secrets.local.json` 是否存在：不存在则引导用户参照 `config/secrets.example.json` 创建——需在网易邮箱网页版「设置 → POP3/SMTP/IMAP」开启 IMAP 服务并生成客户端授权码（163/126/yeah 的 imap_host 分别为 imap.163.com / imap.126.com / imap.yeah.com）

## 流程

1. 读 `data/emails.json`，取 `lastFetchedAt` 的日期作为 `--since`（无记录则用今天）
2. 运行：`python scripts/fetch_emails.py --since YYYY-MM-DD`，从输出确认"新增 N 封"
3. 读 `data/emails.json` 中 `processed=false` 的邮件
4. 读 `data/jobmaster_data.csv`，准备现有投递的企业列表（完整数据模型见 `.trae/rules/project_rules.md`）
5. 逐封判断是否秋招相关：
   - 相关：发件人名称/地址含现有企业名（将企业名与发件人名称剥离「招聘/校招/人才/HR/官方/校园」等通用词后做包含匹配），或主题含关键词：笔试/测评/考试/面试/一面/二面/三面/技术面/主管面/总监面/HR面/offer/录用/简历评估/投递成功/感谢信/进展通知
   - 无关（广告、验证码、订阅、系统通知等）→ 标记 `processed=true, matchedAction='ignored'`
6. 对秋招邮件执行动作：
   - 匹配到现有投递（按企业名，同企业多行时结合岗位/部门关键词消歧，仍无法确定则询问用户）→ 更新 `status`：
     - 简历评估/进入流程 → 简历筛
     - 笔试/测评/考试通知 → 笔试筛
     - 一面/二面/技术面/专业面 → 专业面
     - 主管面/总监面/交叉面 → 主管面
     - HR面 → HR面
     - offer/录用/入职通知 → Offer
     - 感谢信/未通过/不合适 → 已挂
     - 同时 `notes` 追加 `MM-DD 依据（邮件）`，`updatedAt` 更新为当前时间
   - 未匹配到投递且邮件明确是新投递确认 → 新增一行：id 按 `jm_时间戳_4位hex` 规则生成，`type` 向用户确认（互联网/央国企），`status=简历筛`，`source=邮箱提取`
   - 无法确定 → 跳过，在汇总中列为待用户确认
7. 回写两个文件：
   - CSV：全量读改写回（保留 UTF-8 BOM、CRLF、标准转义，表头不变）
   - emails.json：被处理邮件标记 `processed=true`、`matchedEntryId`、`matchedAction`（更新进度/新增投递/ignored）
8. 输出 Markdown 汇总表：日期｜发件人｜主题｜动作｜涉及企业

## 约束

- 授权码绝不回显
- 不确定的信息宁可列为待确认，不要臆造企业名/岗位
- 完成后提醒用户：浏览器打开 index.html 会自动合并这些变更

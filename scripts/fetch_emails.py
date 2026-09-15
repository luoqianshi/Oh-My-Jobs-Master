#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Job-Master 邮箱采集脚本：通过 IMAP 拉取网易邮箱新邮件，追加到 data/emails.json。

用法：
  python scripts/fetch_emails.py                     # 拉取今天的邮件
  python scripts/fetch_emails.py --since 2026-09-15   # 拉取指定日期起的邮件

配置：
  参照 config/secrets.example.json 创建 config/secrets.local.json，
  并在邮箱网页版「设置 → POP3/SMTP/IMAP」中开启 IMAP 服务、生成客户端授权码。
  163 / 126 / yeah 邮箱的 imap_host 分别为 imap.163.com / imap.126.com / imap.yeah.com。

本脚本只负责采集（按 Message-ID 去重后追加），不做任何秋招业务判断；
是否为秋招邮件、如何更新进度，由 Trae Agent 结合 SKILL 处理。
"""
import argparse
import email as email_lib
import imaplib
import json
import os
import random
import sys
from datetime import date, datetime
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(BASE_DIR, '..', 'config', 'secrets.local.json')
DEFAULT_DATA_DIR = os.path.join(BASE_DIR, '..', 'data')


def load_config(path):
    if not os.path.exists(path):
        sys.exit('未找到配置文件 %s\n请参照 config/secrets.example.json 创建 config/secrets.local.json，'
                 '并在邮箱网页版开启 IMAP 服务生成客户端授权码。' % path)
    with open(path, encoding='utf-8') as f:
        cfg = json.load(f)
    for key in ('imap_host', 'email', 'auth_code'):
        if not cfg.get(key):
            sys.exit('配置文件缺少字段 %s' % key)
    return cfg


def decode_str(s):
    """解码邮件头（主题/发件人可能被 base64 或 quoted-printable 编码）"""
    if not s:
        return ''
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return str(s)


def part_snippet(part, limit=300):
    """提取单个邮件分段的纯文本前 N 字"""
    try:
        payload = part.get_payload(decode=True) or b''
    except Exception:
        return ''
    charset = part.get_content_charset() or 'utf-8'
    try:
        text = payload.decode(charset, errors='replace')
    except (LookupError, UnicodeDecodeError):
        text = payload.decode('utf-8', errors='replace')
    return ' '.join(text.split())[:limit]


def body_snippet(msg, limit=300):
    """优先取 text/plain 分段，退而求其次取 text/html"""
    try:
        if msg.is_multipart():
            plain = html = None
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == 'text/plain' and plain is None and not part.is_multipart():
                    plain = part_snippet(part, limit)
                elif ct == 'text/html' and html is None and not part.is_multipart():
                    html = part_snippet(part, limit)
            return plain or html or ''
        return part_snippet(msg, limit)
    except Exception:
        return ''


def gen_email_id():
    return 'em_%d_%04x' % (int(datetime.now().timestamp() * 1000), random.randint(0, 0xFFFF))


def main():
    parser = argparse.ArgumentParser(description='拉取网易邮箱新邮件到 data/emails.json')
    parser.add_argument('--since', default=date.today().isoformat(), help='起始日期 YYYY-MM-DD，默认今天')
    parser.add_argument('--limit', type=int, default=50, help='最多拉取封数，默认 50')
    parser.add_argument('--config', default=DEFAULT_CONFIG, help='配置文件路径')
    parser.add_argument('--data-dir', default=DEFAULT_DATA_DIR, help='数据目录路径')
    args = parser.parse_args()

    cfg = load_config(args.config)
    try:
        since_dt = datetime.strptime(args.since, '%Y-%m-%d')
    except ValueError:
        sys.exit('--since 日期格式应为 YYYY-MM-DD，收到：%s' % args.since)
    since_imap = since_dt.strftime('%d-%b-%Y')  # IMAP 要求 15-Sep-2026 格式

    # 读取现有邮件池，按 Message-ID 去重
    emails_path = os.path.join(args.data_dir, 'emails.json')
    pool = {'lastFetchedAt': None, 'emails': []}
    if os.path.exists(emails_path):
        try:
            with open(emails_path, encoding='utf-8-sig') as f:
                pool = json.load(f)
        except Exception as e:
            sys.exit('读取 %s 失败：%s' % (emails_path, e))
    seen = set(m.get('messageId') for m in pool.get('emails', []) if m.get('messageId'))

    # 连接邮箱
    try:
        mail = imaplib.IMAP4_SSL(cfg['imap_host'], 993)
    except Exception as e:
        sys.exit('无法连接 %s：%s' % (cfg['imap_host'], e))
    try:
        mail.login(cfg['email'], cfg['auth_code'])
    except imaplib.IMAP4.error as e:
        sys.exit('IMAP 登录失败：%s\n请检查邮箱地址与授权码（需为网页版生成的客户端授权码，非登录密码）。' % e)

    # 网易（163/126/yeah）IMAP 要求登录后先发送 ID 命令声明客户端，
    # 否则 SELECT 等后续命令返回 NO（"Unsafe Login"），状态停留在 AUTH。
    if 'ID' not in imaplib.Commands:
        imaplib.Commands['ID'] = ('AUTH', 'SELECTED')
    try:
        typ, dat = mail._simple_command('ID', '("name" "JobMaster" "version" "1.0.0")')
        mail._untagged_response(typ, dat, 'ID')
    except Exception:
        pass  # 服务器不支持 ID 时按原流程继续

    added = []
    try:
        typ, sel_data = mail.select('INBOX', readonly=True)
        if typ != 'OK':
            sys.exit('打开收件箱失败：%s\n若提示 Unsafe Login，请确认已在邮箱网页版开启 IMAP 服务。' % sel_data)
        typ, data = mail.search(None, '(SINCE %s)' % since_imap)
        if typ != 'OK':
            sys.exit('邮件搜索失败：%s' % typ)
        ids = data[0].split()[-args.limit:] if args.limit > 0 else data[0].split()
        for num in ids:
            typ, md = mail.fetch(num, '(RFC822)')
            if typ != 'OK' or not md or not md[0]:
                continue
            msg = email_lib.message_from_bytes(md[0][1])
            mid = (msg.get('Message-ID') or '').strip()
            if mid and mid in seen:
                continue
            if mid:
                seen.add(mid)
            from_name, from_addr = parseaddr(msg.get('From', ''))
            try:
                dt = parsedate_to_datetime(msg.get('Date', '')).isoformat()
            except Exception:
                dt = datetime.now().isoformat(timespec='seconds')
            rec = {
                'id': gen_email_id(),
                'messageId': mid,
                'from': from_addr or msg.get('From', ''),
                'fromName': decode_str(from_name),
                'subject': decode_str(msg.get('Subject', '')),
                'date': dt,
                'snippet': body_snippet(msg),
                'processed': False,
                'matchedEntryId': None,
                'matchedAction': None,
            }
            pool['emails'].append(rec)
            added.append(rec)
    finally:
        try:
            mail.logout()
        except Exception:
            pass

    pool['lastFetchedAt'] = datetime.now().isoformat(timespec='seconds')
    os.makedirs(args.data_dir, exist_ok=True)
    with open(emails_path, 'w', encoding='utf-8') as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)

    print('本次拉取范围：%s 起（最多 %d 封）' % (args.since, args.limit))
    print('新增 %d 封，emails.json 现共 %d 封' % (len(added), len(pool['emails'])))
    for r in added:
        print('  [%s] %s | %s | %s' % (
            r['date'][:16].replace('T', ' '),
            r['fromName'] or '-',
            r['from'],
            r['subject']))
    if not added:
        print('没有新增邮件。')


if __name__ == '__main__':
    main()

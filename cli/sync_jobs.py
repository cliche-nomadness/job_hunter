# cli/sync_jobs.py —— 每日自动同步（轻抓列表版）
#
# 数据流：
#   sites.txt（可抓清单：公司,URL,城市,方向摘要）
#     → Playwright 抓岗位列表（只进列表页，不进详情——请求量降 97%）
#     → 链接密度分类：≥3 个岗位=正常；0 个=可疑（降级公司级行 + 日志提醒人工核对）
#   pending.txt（待人工细化：公司,URL,城市,方向摘要,原因）
#     → 不抓取，直接写"公司级行"兜底（岗位名=表格方向摘要，细化后重跑会被具体岗位行并存/替换）
#   → 全部合并进 jobs.csv（JD 列 = 表格方向摘要；具体 JD 在"优化简历"时按需抓单条）
#
# 用法：..\.venv\Scripts\python.exe sync_jobs.py
#   快速模式（开发调试用，30 秒验证链路）：
#     ..\.venv\Scripts\python.exe sync_jobs.py --limit 3            # 只跑前 3 站
#     ..\.venv\Scripts\python.exe sync_jobs.py --only 远景能源,滴滴   # 只跑指定公司
#   同步完成后自动推送岗位播报到飞书：新增岗位 + 按意向关键词筛出的"与你相关"
#   （关键词在 .env 配 POSITION_KEYWORDS，逗号分隔；推送目标自动发现，见 feishu_api.py）
#   入库过滤：只有岗位名命中 POSITION_KEYWORDS 的岗位才写进 jobs.csv（公司级行同理）
#   ——全量抓、按意向存；想临时全量入库加 --no-filter
import sys
import os
import csv
import time
from pathlib import Path
from datetime import datetime

from job_provider_moka import scrape_job_list
from playwright.sync_api import sync_playwright

import feishu_api

BASE_DIR = Path(__file__).resolve().parent.parent
CLI_DIR = Path(__file__).resolve().parent
SITES_FILE = CLI_DIR / "sites.txt"
PENDING_FILE = CLI_DIR / "pending.txt"
JOBS_FILE = BASE_DIR / "jobs.csv"
LOG_FILE = BASE_DIR / "logs" / "sync.log"

FALLBACK_TITLE = "（待人工细化岗位方向）"   # 方向摘要为空时的占位岗位名
PUSH_TOP_N = 10                             # 推送里最多列几个相关岗位
DEFAULT_KEYWORDS = "AI,算法,大模型,Agent,LLM,机器学习"


def push_keywords():
    """意向关键词：.env 的 POSITION_KEYWORDS 优先，否则默认（面向 AI 应用/Agent 岗）。"""
    raw = os.environ.get("POSITION_KEYWORDS", "") or DEFAULT_KEYWORDS
    return [k.strip() for k in raw.split(",") if k.strip()]


def is_relevant(title, jd, keywords):
    """岗位名或方向摘要命中任一关键词 = 相关（大小写不敏感的子串匹配）。"""
    text = f"{title} {jd}".lower()
    return any(k.lower() in text for k in keywords)


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        # 日志文件被占用（Excel/WPS 打开、同步软件扫描等）→ 只提示，不让日志杀死同步
        print(f"⚠️ 日志写入失败（文件可能被别的程序占用）: {e}", flush=True)


def _parse_site_line(line):
    """解析 '公司,URL[,城市,方向摘要[,原因]]' 行 → dict（列数可变，原因列忽略）。"""
    parts = [p.strip() for p in line.split(",", 4)]
    if len(parts) < 2:
        return None
    if not parts[1].lower().startswith(("http://", "https://")):
        return None  # URL 必须是 http(s)——防"武汉市,各学科教师"这类污染行被当站点去抓
    return {"company": parts[0], "url": parts[1],
            "city": parts[2] if len(parts) > 2 else "",
            "summary": parts[3] if len(parts) > 3 else ""}


def load_sites(only=None, limit=None):
    """读可抓清单 sites.txt；--only 按公司名过滤，--limit 只取前 N 站（开发调试用）。"""
    sites = []
    for line in SITES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        site = _parse_site_line(line)
        if site:
            sites.append(site)
        else:
            log(f"⚠️ 清单行格式错误，跳过: {line}")
    if only:
        sites = [s for s in sites if s["company"] in only]
        missing = set(only) - {s["company"] for s in sites}
        if missing:
            log(f"⚠️ --only 里的公司不在清单中: {','.join(missing)}")
    if limit:
        sites = sites[:limit]
    return sites


def load_pending():
    """读待细化清单 pending.txt（文件不存在返回空）。"""
    if not PENDING_FILE.exists():
        return []
    rows = []
    for line in PENDING_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        site = _parse_site_line(line)
        if site:
            rows.append(site)
    return rows


def load_jobs_csv():
    with open(JOBS_FILE, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save_jobs_csv(rows):
    fieldnames = ["公司", "岗位", "城市", "JD", "链接"]
    with open(JOBS_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def detail_url(job):
    detail = job.get("detail", "")
    if detail.startswith("http"):
        return detail
    base = job.get("base", "")
    return base + detail if detail.startswith("#") else base.rstrip("/") + detail


def upsert(rows, company, title, url, city="", jd=""):
    """按【公司+岗位】联合主键匹配更新；没匹配到就新增。

    公司+岗位是联合主键——多公司同名岗位（"算法工程师"到处都是）不会互相覆盖。
    """
    for row in rows:
        if row["公司"] == company and row["岗位"] == title:
            row["链接"] = url
            if city:
                row["城市"] = city
            if jd:
                row["JD"] = jd
            return "更新"
    rows.append({"公司": company, "岗位": title, "城市": city, "JD": jd, "链接": url})
    return "新增"


def sync_site(site, browser):
    """轻抓一个站点：只抓列表页。返回岗位列表；可疑/失败返回 None（降级公司级行）。"""
    company, url = site["company"], site["url"]
    log(f"开始同步 {company}: {url}")
    try:
        jobs = scrape_job_list(url, browser)  # 复用整轮唯一的浏览器实例
    except Exception as e:
        log(f"  ❌ 抓取失败: {e}——降级写公司级行")
        return None
    if not jobs:
        log("  ⚠️ 抓到 0 个岗位——疑似非岗位列表页，降级写公司级行，请人工核对 URL")
        return None
    log(f"  ✅ 抓到 {len(jobs)} 个岗位（轻抓列表，不进详情）")
    return jobs


def _run(only=None, limit=None, no_filter=False):
    rows = load_jobs_csv()
    sites = load_sites(only, limit)
    keywords = push_keywords()
    log(f"本轮 {len(sites)} 个站点，浏览器全程复用（整轮只启动一次）；意向关键词: {','.join(keywords)}"
        + ("；入库过滤：关（--no-filter）" if no_filter else "；入库过滤：开（只存岗位名命中的）"))
    ok = suspicious = 0
    new_jobs = []       # 本轮"新增"的具体岗位行（公司级行不算——避免首跑刷屏）
    relevant_total = 0  # 本轮命中的相关岗位行数（含已在库的"更新"）——推送里报总数
    filtered_out = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        try:
            for site in sites:
                jobs = sync_site(site, browser)
                if jobs:
                    ok += 1
                    kept = 0
                    for j in jobs:
                        # 入库过滤：岗位名不命中意向关键词就不写 jobs.csv（开源用户改 .env 即可自定义）
                        if not no_filter and not is_relevant(j["title"], "", keywords):
                            filtered_out += 1
                            continue
                        action = upsert(rows, site["company"], j["title"], detail_url(j),
                                        site["city"], site["summary"])
                        if action == "新增":
                            new_jobs.append({"公司": site["company"], "岗位": j["title"],
                                             "城市": site["city"], "JD": site["summary"],
                                             "链接": detail_url(j)})
                        kept += 1
                    log(f"  写入 {kept} 行具体岗位（过滤 {len(jobs) - kept} 行，最新: {jobs[-1]['title']}）")
                    relevant_total += kept   # kept = 本轮入库的相关岗位行数（新增+更新）
                else:
                    suspicious += 1
                    # 公司级行兜底：岗位名=表格方向摘要（同样过入库过滤）
                    fb_title = site["summary"] or FALLBACK_TITLE
                    if not no_filter and not is_relevant(fb_title, "", keywords):
                        filtered_out += 1
                        log(f"  ⛔ 公司级行未命中意向关键词，不入库: {fb_title}")
                        continue
                    action = upsert(rows, site["company"], fb_title,
                                    site["url"], site["city"], "【公司级·待细化】")
                    log(f"  {action}（公司级）: {fb_title}")
                save_jobs_csv(rows)     # 每站落盘一次——中途崩了也有已完成部分
                time.sleep(2)           # 站点间停顿，防限流
        finally:
            browser.close()

    # pending.txt → 不抓取，直接公司级行兜底（同样过入库过滤）
    pendings = load_pending()
    for p in pendings:
        fb_title = p["summary"] or FALLBACK_TITLE
        if not no_filter and not is_relevant(fb_title, "", keywords):
            filtered_out += 1
            continue
        upsert(rows, p["company"], fb_title, p["url"], p["city"], "【公司级·待细化】")
    if pendings:
        log(f"pending 兜底：{len(pendings)} 家处理（细化后重跑即被具体岗位行取代）")

    save_jobs_csv(rows)
    log(f"同步完成：{ok} 个站点抓到岗位，{suspicious} 个可疑；"
        f"过滤掉 {filtered_out} 行不相关；jobs.csv 共 {len(rows)} 行")
    push_report(new_jobs, relevant_total, ok, suspicious)


def push_report(new_jobs, relevant_total, ok, suspicious):
    """同步后推送岗位播报——**每日必发**（无新增也发心跳）。

    语义分清两层（"相关 0 个≠筛选坏了"的教训）：
      relevant_total = 本轮命中的相关岗位行数（新增+已在库的更新）
      new_jobs       = 其中"新增"的部分（库里之前没有的）
    每天固定收到 = 机器活着的心跳；哪天没收到 = 定时任务/机器人挂了，主动暴露故障。
    推送失败只记日志，绝不影响同步结果。
    """
    try:
        keywords = push_keywords()
        # 入库过滤已保证 new_jobs 全部命中关键词，直接用
        lines = [
            f"📡 校招虾每日播报 | {datetime.now():%m-%d %H:%M}",
            f"本轮：成功 {ok} 站 / 可疑 {suspicious} 站；相关岗位 {relevant_total} 个（新增 {len(new_jobs)}）",
            f"🎯 意向关键词: {','.join(keywords)}",
        ]
        if new_jobs:
            for i, j in enumerate(new_jobs[:PUSH_TOP_N], 1):
                lines.append(f"{i}. {j['公司']} | {j['岗位']} | {j['城市'] or '未标注'}")
                lines.append(f"   {j['链接']}")
            if len(new_jobs) > PUSH_TOP_N:
                lines.append(f"...其余 {len(new_jobs) - PUSH_TOP_N} 个已入库，发「岗位 关键词」查看")
        elif relevant_total:
            lines.append(f"本轮无新增——{relevant_total} 个相关岗位都已在库，发「岗位 关键词」查看")
        else:
            lines.append("今日暂无相关岗位——所有站点都盘点过了")
        target, id_type = feishu_api.resolve_push_target()
        feishu_api.send_text(target, "\n".join(lines), receive_id_type=id_type)
        log(f"推送完成：相关 {relevant_total}，新增 {len(new_jobs)}")
    except Exception as e:
        log(f"⚠️ 推送失败（不影响同步结果）: {e}")


def main():
    only = limit = None
    no_filter = "--no-filter" in sys.argv
    if "--only" in sys.argv:
        only = [s.strip() for s in sys.argv[sys.argv.index("--only") + 1].split(",") if s.strip()]
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    try:
        _run(only, limit, no_filter)
    except Exception:
        # 兜底：任何没料到的异常都写进日志（日志是唯一现场）
        import traceback
        log("❌ 同步失败，未捕获异常：\n" + traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

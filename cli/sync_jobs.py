# cli/sync_jobs.py —— 每日自动同步：抓列表 → 抓全部JD → 合并进 jobs.csv → 写日志
#
# 站点清单 cli/sites.txt（每行：公司名,岗位列表URL；# 开头是注释）：
#   远景,https://app.mokahr.com/campus_apply/envisiongroup/43123#/jobs
#
# 用法：
#   ..\.venv\Scripts\python.exe sync_jobs.py            # 同步所有站点
#   ..\.venv\Scripts\python.exe sync_jobs.py --limit 3  # 调试：每站只抓前 3 个岗位的 JD
import sys
import csv
import json
import time
from pathlib import Path
from datetime import datetime

from job_provider_moka import scrape_job_list, scrape_job_detail

BASE_DIR = Path(__file__).resolve().parent.parent
CLI_DIR = Path(__file__).resolve().parent
SITES_FILE = CLI_DIR / "sites.txt"
JOBS_FILE = BASE_DIR / "jobs.csv"
LOG_FILE = BASE_DIR / "logs" / "sync.log"


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


def load_sites():
    """读站点清单 → [(公司名, URL)]；空行和 # 注释跳过。"""
    sites = []
    for line in SITES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 1)
        if len(parts) == 2:
            sites.append((parts[0].strip(), parts[1].strip()))
        else:
            log(f"⚠️ 清单行格式错误，跳过: {line}")
    return sites


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


def upsert(rows, company, title, jd, url):
    """匹配更新；没匹配到就新增（公司名来自站点清单）。"""
    for row in rows:
        if title == row["岗位"]:
            row["JD"] = jd
            row["链接"] = url
            return "更新"
    rows.append({"公司": company, "岗位": title, "城市": "", "JD": jd, "链接": url})
    return "新增"


def sync_site(company, url, limit=None):
    """同步一个站点：抓列表 → 逐个抓 JD。单个失败不中断。"""
    log(f"开始同步 {company}: {url}")
    jobs = scrape_job_list(url)
    log(f"  抓到 {len(jobs)} 个岗位，开始抓 JD...")
    for i, j in enumerate(jobs):
        if limit and i >= limit:
            log(f"  --limit {limit}，停止")
            break
        try:
            time.sleep(2)                                  # 请求间停顿，防限流
            jd = scrape_job_detail(j["base"], j["detail"])
            j["jd"] = jd
            log(f"  [{i+1}/{len(jobs)}] {j['title']} JD {len(jd)} 字")
        except Exception as e:
            log(f"  [{i+1}/{len(jobs)}] {j['title']} 抓取失败: {e}")   # 不中断
    return jobs


def _run(limit=None):
    rows = load_jobs_csv()
    for company, url in load_sites():
        jobs = sync_site(company, url, limit)
        for j in jobs:
            if not j.get("jd"):
                continue                                   # 没抓到的跳过
            action = upsert(rows, company, j["title"], j["jd"], detail_url(j))
            log(f"  {action}: {j['title']}")
    save_jobs_csv(rows)
    log(f"同步完成，jobs.csv 现有 {len(rows)} 行")


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    try:
        _run(limit)
    except Exception:
        # 兜底：任何没料到的异常都写进日志（cmd 不再重定向，日志是唯一现场）
        import traceback
        log("❌ 同步失败，未捕获异常：\n" + traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

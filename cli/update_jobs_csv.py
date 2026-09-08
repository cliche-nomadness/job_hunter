# cli/update_jobs_csv.py —— 把 job_provider_moka 抓到的岗位合并进 jobs.csv
#
# v2 变化（上一版只做"匹配更新"，静默跳过没 JD 的岗位）：
#   1. 没匹配到现有岗位时 → 用命令行给的【公司名】新增一行（而不是静默跳过）
#   2. 没抓 JD 的岗位 → 打印跳过提示（诊断友好，不装死）
#
# 用法：
#   ..\.venv\Scripts\python.exe job_provider_moka.py "<URL>" 3 jobs_out.json  # 先抓（序号3的JD）
#   ..\.venv\Scripts\python.exe update_jobs_csv.py jobs_out.json 远景集团     # 再合并
import json
import csv
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
JOBS_FILE = BASE_DIR / "jobs.csv"          # 和 server.py 用的同一个文件


def load_jobs_csv():
    """读 jobs.csv → 行字典列表。utf-8-sig 兼容 Excel 的 BOM 头。"""
    with open(JOBS_FILE, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save_jobs_csv(rows):
    """把行列表写回 jobs.csv（保留原表头顺序）。"""
    fieldnames = ["公司", "岗位", "城市", "JD", "链接"]
    with open(JOBS_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def detail_url(job):
    """把 {base, detail} 拼成完整链接（base 是站根，detail 是 #/job/xxx）。"""
    detail = job.get("detail", "")
    if detail.startswith("http"):
        return detail
    base = job.get("base", "")
    return base + detail if detail.startswith("#") else base.rstrip("/") + detail


def main():
    if len(sys.argv) < 2:
        print("用法: python update_jobs_csv.py <jobs_out.json> [公司名]")
        print("  例: python update_jobs_csv.py jobs_out.json 远景集团")
        sys.exit(1)

    company = sys.argv[2] if len(sys.argv) >= 3 else ""

    with open(sys.argv[1], encoding="utf-8") as f:
        scraped = json.load(f)             # [{title, meta, detail, base, jd?}]

    rows = load_jobs_csv()
    updated = added = skipped = 0

    for job in scraped:
        title = job.get("title", "").strip()
        jd = job.get("jd", "").strip()
        if not jd:
            skipped += 1
            print(f"⏭️ 跳过（没抓JD）: {title}")
            continue

        # 策略一：按岗位名匹配 → 更新现有行的 JD
        matched = False
        for row in rows:
            if title == row["岗位"]:
                row["JD"] = jd
                row["链接"] = detail_url(job)
                updated += 1
                print(f"✅ 更新: {title}")
                matched = True
                break

        # 策略二：csv 里没有 → 新增一行（公司名来自命令行参数）
        if not matched:
            if not company:
                print(f"⚠️ 没匹配到「{title}」，且没给公司名 → 跳过（用法加公司名参数）")
                continue
            rows.append({
                "公司": company,
                "岗位": title,
                "城市": "",
                "JD": jd,
                "链接": detail_url(job),
            })
            added += 1
            print(f"➕ 新增: {company} - {title}")

    save_jobs_csv(rows)
    print(f"\n完成: 更新{updated} 新增{added} 跳过{skipped} → {JOBS_FILE}")


if __name__ == "__main__":
    main()

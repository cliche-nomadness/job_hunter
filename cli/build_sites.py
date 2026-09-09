# cli/build_sites.py —— 腾讯智能表格 → sites.txt（可抓清单）+ pending.txt（待人工细化）
#
# 链路：表格记录 → 清洗公司名 → 短链展开 → 平台指纹分类 → 去重 → 写两份清单
#
# 跑法（低频/手动——公司列表不常变，token 过期只影响这一步，不影响每日抓取）：
#   ..\.venv\Scripts\python.exe build_sites.py                                    # 全量
#   ..\.venv\Scripts\python.exe build_sites.py --limit 50                         # 只处理前 50 条
#   ..\.venv\Scripts\python.exe build_sites.py --limit 50 --exclude 暑期实习,日常实习
#       （--exclude 按"招聘类型"字段过滤，先排除再限量；多个关键字用英文逗号分隔）
# token 放在 cli/.env：TENCENT_MCP_TOKEN=...（获取方式见 read_smartsheet.py 注释）
#
# 产物格式（sync_jobs.py 读取）：
#   sites.txt   公司,URL,城市,方向摘要      （后两列可选，# 开头是注释）
#   pending.txt 公司,URL,城市,方向摘要,原因  （人工在表格里把 URL 细化成岗位列表页后重跑本脚本）
#
# 单一数据源：人工细化一律改【表格】，再重跑本脚本重新生成——sites.txt 是产物，不是编辑对象。

import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()  # 从 cli/.env 读 TENCENT_MCP_TOKEN

from read_smartsheet import FILE_ID, SHEET_ID, rpc, parse_tool_result, flatten_record

CLI_DIR = Path(__file__).resolve().parent
SITES_FILE = CLI_DIR / "sites.txt"
PENDING_FILE = CLI_DIR / "pending.txt"

# 平台指纹：【域名】里出现这些词 → 大概率是招聘系统/岗位页（mokahr 已实测验证可抓）
# 只匹配域名不匹配路径——路径里出现 job/hr 等字样太常见（hr-page、thread 都会撞）
ATS_FINGERPRINTS = (
    "mokahr.com", "zhiye.com", "beisen.com", "zhaopin", "51job.com", "liepin.com",
    "hotjob", "gllue", "jobmd", "talent", "career", "campus", "job", "recruit", "xyz",
)


def clean_company(name):
    """公司名去掉结尾括号备注：'远景能源（注意看后面的备注~）' → '远景能源'。"""
    prev = None
    while prev != name:
        prev = name
        name = re.sub(r"[（(][^（）()]*[）)]\s*$", "", name).strip()
    return name


def clean_text(text):
    """字段内换行符换成 '、'——防止写清单文件时一行被拆成多行（换行污染）。"""
    return re.sub(r"\s*\n\s*", "、", text).strip()


def expand_url(url, timeout=15):
    """短链展开：跟随重定向拿最终 URL。失败返回 (原URL, False)——交给分类器判 pending。"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout, headers=headers)
        if r.status_code < 400 and r.url:
            return r.url, True
    except requests.RequestException:
        pass
    try:  # 有的短链拒绝 HEAD → GET 兜底（stream=True 不下载正文）
        r = requests.get(url, allow_redirects=True, timeout=timeout,
                         stream=True, headers=headers)
        final = r.url
        r.close()
        return final, True
    except requests.RequestException:
        return url, False


def _page_key(url):
    """页面标识 = 域名+路径（忽略 query/fragment）——同页不同内推码/分享token 只算一个站点。"""
    p = urlparse(url or "")
    return f"{p.netloc.lower()}{p.path.rstrip('/')}"


def classify(url):
    """平台指纹分类（只看域名）：'ready'（大概率可抓）| 'pending'（未知域名，待人工确认）。"""
    host = urlparse(url or "").netloc.lower()
    return "ready" if any(f in host for f in ATS_FINGERPRINTS) else "pending"


def build_from_records(records, expand=True):
    """主流程纯逻辑（可离线测试）：表格记录 → (sites, pending)。

    expand=False 时跳过短链展开（离线测试用），按原 URL 分类。
    每家公司唯一归属：有一条可抓链接就进 sites，否则进 pending（内推码不同的
    重复记录、同一公司多条记录都会折叠成一条）。
    """
    sites, pending, seen = [], [], set()
    taken = {}                                   # company -> 'ready' | 'pending'
    page_taken = set()                           # host+path 全局去重（同页不同内推码/分享token）
    for rec in records:
        row = flatten_record(rec)
        company = clean_company(row.get("招聘企业", "") or "")
        url = (row.get("投递链接", "") or "").strip()
        city = clean_text(row.get("工作地点", "") or "")
        summary = clean_text(row.get("招聘岗位", "") or "")
        if not company or not url:
            continue  # 缺公司名或链接的记录无法使用

        final_url, ok = expand_url(url) if expand else (url, True)
        if ok:
            category = classify(final_url)
            reason = "" if category == "ready" else "非已知ATS域名，请人工确认岗位列表页"
        else:
            category, reason = "pending", "短链展开失败"

        key = (company, final_url)
        if key in seen:
            continue                             # 同公司同链接的重复记录
        seen.add(key)
        # 同一页面（域名+路径相同，仅内推码/分享token不同）只保留第一条
        page_key = _page_key(final_url)
        if category == "ready" and page_key in page_taken:
            continue
        if taken.get(company) == "ready":
            continue                             # 该公司已有可抓链接，后续全跳过
        if taken.get(company) == "pending" and category == "pending":
            continue                             # 已有一条待细化，不重复收

        if category == "ready":
            sites.append({"company": company, "url": final_url,
                          "city": city, "summary": summary})
            page_taken.add(page_key)
        else:
            # pending 写"用户能打开的链接"：展开失败留原短链，否则用展开后的
            pending.append({"company": company, "url": final_url if ok else url,
                            "city": city, "summary": summary, "reason": reason})
        taken[company] = category

    # 公司唯一归属：后发现的 ready 从 pending 里摘除
    ready_names = {s["company"] for s in sites}
    pending = [p for p in pending if p["company"] not in ready_names]
    return sites, pending


def filter_records(records, limit=None, excludes=()):
    """记录预处理：先按"招聘类型"排除不要的（如过时的暑期实习），再限量截断。

    顺序很重要：先排除再限量，--limit 50 才是"要 50 条想要的"，而不是"50 条里碰运气"。
    全量过滤后再截断（不用 break 提前退）——排除统计才准确；
    过滤发生在短链展开之前，被排除的记录依然不做任何网络请求。
    """
    kept, excluded = [], 0
    for rec in records:
        row = flatten_record(rec)
        rtype = row.get("招聘类型", "") or ""
        if any(k in rtype for k in excludes):
            excluded += 1
            continue
        kept.append(rec)
    if limit:
        kept = kept[:limit]
    return kept, excluded


def parse_args(argv):
    """手动解析 --limit N / --exclude 关键字1,关键字2（风格与 sync_jobs 一致）。"""
    limit, excludes = None, []
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    if "--exclude" in argv:
        excludes = [k.strip() for k in argv[argv.index("--exclude") + 1].split(",")
                    if k.strip()]
    return limit, excludes


def fetch_all_records(token):
    """分页读全表（limit 上限 100，has_more/next 翻页）。

    注意：不传 view_id——传了会读"特定视图"的数据（可能带筛选/排序，
    不是你眼前看到的完整表格）；不传 = 默认视图 = 全部记录。
    """
    all_rows, offset = [], 0
    while True:
        page = parse_tool_result(rpc(token, "smartsheet.list_records", {
            "file_id": FILE_ID, "sheet_id": SHEET_ID,
            "limit": 100, "offset": offset,
        }))
        if page.get("error"):
            sys.exit(f"读取记录失败: {page['error']}")
        all_rows.extend(page["records"])
        if not page.get("has_more"):
            return all_rows
        offset = page["next"]


def main():
    token = os.environ.get("TENCENT_MCP_TOKEN", "")
    if not token:
        sys.exit("缺 TENCENT_MCP_TOKEN：请在 cli/.env 里添加（获取方式见 read_smartsheet.py 注释）")

    limit, excludes = parse_args(sys.argv)
    records = fetch_all_records(token)
    print(f"读取 {len(records)} 条记录")

    kept, excluded = filter_records(records, limit=limit, excludes=excludes)
    note = f"，类型排除 {excluded} 条（{ '、'.join(excludes) }）" if excludes else ""
    print(f"处理 {len(kept)} 条{note}，开始清洗/展开/分类（短链展开较慢，请稍候）...")

    sites, pending = build_from_records(kept)

    SITES_FILE.write_text(
        "# 由 build_sites.py 生成（请勿手编——细化改表格后重跑本脚本）：公司,URL,城市,方向摘要\n"
        + "\n".join(f'{s["company"]},{s["url"]},{s["city"]},{s["summary"]}' for s in sites)
        + "\n",
        encoding="utf-8")
    PENDING_FILE.write_text(
        "# 待人工细化：打开 URL 找到岗位列表页 → 在表格里更新投递链接 → 重跑本脚本。"
        "格式：公司,URL,城市,方向摘要,原因\n"
        + "\n".join(f'{p["company"]},{p["url"]},{p["city"]},{p["summary"]},{p["reason"]}'
                    for p in pending)
        + "\n",
        encoding="utf-8")

    print(f"✅ sites.txt：{len(sites)} 家可抓")
    print(f"⚠️ pending.txt：{len(pending)} 家待人工细化（打开链接确认列表页后改表格）")


if __name__ == "__main__":
    main()

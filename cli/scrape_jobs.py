# cli/scrape_jobs.py —— 从公司招聘官网抓取岗位（列表 + 单条 JD），通用，Moka 已验证
#
# 用法（用系统 Edge，免下载 Chromium）：
#   ..\.venv\Scripts\python.exe scrape_jobs.py "<岗位列表URL>"            # 抓岗位列表
#   ..\.venv\Scripts\python.exe scrape_jobs.py "<岗位列表URL>" 0          # 抓第 0 个岗位的 JD
#
# 依赖：pip install playwright（用系统浏览器，无需 playwright install chromium）
#
# 说明：
#   - 这是把之前几个探针/脚本（verify_moka / scrape_moka_jobs / scrape_moka_jd / probe_*）
#     整合成的干净产物：一个入口，列表 + JD。
#   - Moka 已验证可用（岗位详情是 #/job/{id}）；其它平台若 id 在 JS 里（如 zhiye），
#     列表仍能抓标题，JD 需看平台适配。

import sys
import re
import time
from playwright.sync_api import sync_playwright

# 岗位详情链接模式（Moka 的 #/job/{id}；也兼容 /job/、jobAdId= 等常见形态）
LINK_RE = re.compile(r"#/job/|/job/|jobAdId=")

# 卡片文本里的"标签行"，提取标题时要滤掉
TAG_LINES = {"急", "热", "new", "NEW", "|"}


def _open(page, url, wait=8000, retries=3):
    """打开页面并等待渲染。网络抖动时自动重试（国内站偶发超时很常见）。"""
    for attempt in range(1, retries + 1):
        try:
            page.goto(url, timeout=100000, wait_until="load")
            break
        except Exception as e:
            if attempt == retries:
                raise
            print(f"  ⚠️ 第 {attempt} 次连接失败（{e}），3 秒后重试...")
            time.sleep(3)
    page.wait_for_timeout(wait)


def _split_job_text(text):
    """把岗位卡片文本拆成 标题 + 元信息（尽力而为，容忍重复行）。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lines = [ln for ln in lines if ln not in TAG_LINES]
    if not lines:
        return "", ""
    title = lines[0]                                   # 第一行通常是岗位名
    meta = " | ".join(dict.fromkeys(lines[1:]))        # 其余行去重拼成元信息
    return title, meta


def scrape_job_list(url):
    """打开岗位列表页，返回 [{title, meta, detail, base}]。"""
    base = url.split("#")[0]
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        _open(page, url)

        seen = set()
        for a in page.locator("a").all():
            try:
                href = a.get_attribute("href") or ""
            except Exception:
                continue
            if not LINK_RE.search(href) or href in seen:
                continue
            seen.add(href)
            title, meta = _split_job_text((a.inner_text() or "").strip())
            jobs.append({"title": title, "meta": meta, "detail": href, "base": base})
        browser.close()
    return jobs


def scrape_job_detail(base, detail):
    """进入岗位详情页，返回该页的全部可见文本（含 JD）。"""
    if detail.startswith("http"):
        job_url = detail
    else:
        # 兼容 "#/job/xxx"（相对 base）与 "/job/xxx"（站点根）
        job_url = base + detail if detail.startswith("#") else base.rstrip("/") + detail
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        _open(page, job_url)
        full = page.inner_text("body")
        browser.close()
    return full


def main():
    if len(sys.argv) < 2:
        print("用法: python scrape_jobs.py <岗位列表URL> [岗位序号]")
        print("  例: python scrape_jobs.py \"https://app.mokahr.com/campus_apply/envisiongroup/43123#/jobs\"")
        sys.exit(1)

    url = sys.argv[1]
    jobs = scrape_job_list(url)

    if not jobs:
        print("没抓到岗位。可能：")
        print("  1. 站点不把岗位做成 <a> 链接（如 zhiye 用 JS 状态）→ 需平台适配；")
        print("  2. 页面没渲染完 → 可加大 _open 的 wait；")
        print("  3. URL 不对 / 需要登录。")
        return

    print(f"✅ 抓到 {len(jobs)} 个岗位：\n")
    for i, j in enumerate(jobs):
        print(f"[{i}] {j['title']}  | {j['meta']}")
        print(f"     详情: {j['detail']}\n")

    if len(sys.argv) >= 3:
        idx = int(sys.argv[2])
        if 0 <= idx < len(jobs):
            j = jobs[idx]
            print(f"===== 抓取第 {idx} 个岗位的 JD =====\n")
            time.sleep(2)   # 两次请求间稍作停顿，降低被限流概率
            jd = scrape_job_detail(j["base"], j["detail"])
            print(jd[:2000])
        else:
            print(f"序号 {idx} 超出范围（0~{len(jobs)-1}）")


if __name__ == "__main__":
    main()

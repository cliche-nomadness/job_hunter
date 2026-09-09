# cli/job_provider_moka.py —— Moka 平台岗位采集（列表 + JD），输出 JSON
#
# 用法（用系统 Edge，免下载 Chromium）：
#   ..\.venv\Scripts\python.exe job_provider_moka.py "<岗位列表URL>"              # 抓列表
#   ..\.venv\Scripts\python.exe job_provider_moka.py "<岗位列表URL>" 0            # 抓第 0 个的 JD
#   ..\.venv\Scripts\python.exe job_provider_moka.py "<岗位列表URL>" 0 jobs_out.json  # 并存 JSON
#
# 设计：把 scrape_jobs.py 的"通用抓取"升级为"正式 Provider"——列表 + JD + JSON 一条龙。

import sys
import re
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

LINK_RE = re.compile(r"#/job/|/job/|jobAdId=|/position/\d|positionId=|jobPostId=")
TAG_LINES = {"急", "热", "new", "NEW", "|"}
JD_START = re.compile(r"职位描述|岗位职责|工作职责|岗位要求|任职要求")
JD_END = re.compile(r"联系方式|简历投递|申请职位|立即投递|分享职位")


def _open(page, url, wait=8000, retries=3, timeout=100000):
    """打开页面并等待渲染。网络抖动时自动重试（国内站偶发超时很常见）。"""
    for attempt in range(1, retries + 1):
        try:
            page.goto(url, timeout=timeout, wait_until="load")
            break
        except Exception as e:
            if attempt == retries:
                raise
            print(f"  ⚠️ 第 {attempt} 次连接失败（{e}），3 秒后重试...")
            time.sleep(3)
    if wait:
        page.wait_for_timeout(wait)


def _wait_jobs(page, max_wait=10000, need=3):
    """智能等待：轮询岗位链接数量，数量稳定且够数才放行。

    SPA 是渐进渲染——只判"凑够 3 个"会放行太早（远景 36 行只抓到 8 行的教训）；
    判"连续两次轮询数量不再增长"才能抓全。上限 max_wait 毫秒兜底。
    """
    waited, prev, stable = 0, -1, 0
    while waited < max_wait:
        try:
            hrefs = page.eval_on_selector_all(
                "a", "els => els.map(e => e.getAttribute('href') || '')")
        except Exception:
            return
        count = sum(1 for h in hrefs if LINK_RE.search(h or ""))
        if count >= need and count == prev:
            stable += 1
            if stable >= 2:          # 连续 2 次（约 1 秒）数量没涨 → 渲染完成
                return
        else:
            stable = 0
        prev = count
        page.wait_for_timeout(500)
        waited += 500


def _split_job_text(text):
    """把岗位卡片文本拆成 标题 + 元信息（尽力而为，容忍重复行）。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lines = [ln for ln in lines if ln not in TAG_LINES]
    if not lines:
        return "", ""
    title = lines[0]
    meta = " | ".join(dict.fromkeys(lines[1:]))
    return title, meta


def extract_jd(full_text):
    """从整页文本里切出 JD 区段（找不到关键词就整段返回，兜底）。"""
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    start = next((i for i, ln in enumerate(lines) if JD_START.search(ln)), None)
    if start is None:
        return full_text[:2000]
    jd = []
    for ln in lines[start:]:
        if JD_END.search(ln) and len(jd) > 1:   # 标题+至少1行正文后才认收尾词（短JD也能正确切）
            break
        jd.append(ln)
    return "\n".join(jd)


def scrape_job_list(url, browser=None):
    """打开岗位列表页，返回 [{title, meta, detail, base}]。

    browser 传 None：自建浏览器用完即关（CLI 单站用法，行为同旧版）。
    browser 传已有实例：只开一个新标签页——批量抓取时全程复用一个浏览器，
    省掉每站 2~5 秒的冷启动（sync_jobs 每日同步的关键提速点）。
    """
    base = url.split("#")[0]
    if browser is not None:
        return _scrape_list_on(browser, url, base)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        try:
            return _scrape_list_on(b, url, base)
        finally:
            b.close()


def _scrape_list_on(browser, url, base):
    page = browser.new_page()
    try:
        _open(page, url, wait=0, retries=1, timeout=30000)  # 列表页：失败就降级，不值得等 5 分钟
        _wait_jobs(page, max_wait=8000)
        seen = set()
        jobs = []
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
        return jobs
    finally:
        page.close()


def scrape_job_detail(base, detail, browser=None):
    """进入岗位详情页，返回切分后的 JD 区段（browser 语义同 scrape_job_list）。"""
    if detail.startswith("http"):
        job_url = detail
    else:
        job_url = base + detail if detail.startswith("#") else base.rstrip("/") + detail
    if browser is not None:
        return _detail_on(browser, job_url)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        try:
            return _detail_on(b, job_url)
        finally:
            b.close()


def _detail_on(browser, job_url):
    page = browser.new_page()
    try:
        _open(page, job_url, wait=8000, retries=1, timeout=30000)
        return extract_jd(page.inner_text("body"))
    finally:
        page.close()


def main():
    if len(sys.argv) < 2:
        print("用法: python job_provider_moka.py <岗位列表URL> [岗位序号] [输出JSON]")
        sys.exit(1)

    url = sys.argv[1]
    jobs = scrape_job_list(url)
    if not jobs:
        print("没抓到岗位。可能：1) 站点不把岗位做成 <a>（如 zhiye）→ 需 XHR 适配；"
              "2) 页面没渲染完 → 加大 _open 的 wait；3) URL 不对/需登录。")
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
            time.sleep(2)                      # 请求间停顿，降低被限流概率
            jd = scrape_job_detail(j["base"], j["detail"])
            j["jd"] = jd
            print(jd[:2000])
        else:
            print(f"序号 {idx} 超出范围（0~{len(jobs)-1}）")

    if len(sys.argv) >= 4:                     # 存 JSON（列表 + 抓到的 JD）
        out_path = sys.argv[3]
        Path(out_path).write_text(
            json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n💾 已保存: {out_path}")


if __name__ == "__main__":
    main()

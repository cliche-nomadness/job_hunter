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

LINK_RE = re.compile(r"#/job/|/job/|jobAdId=")
TAG_LINES = {"急", "热", "new", "NEW", "|"}
JD_START = re.compile(r"职位描述|岗位职责|工作职责|岗位要求|任职要求")
JD_END = re.compile(r"联系方式|简历投递|申请职位|立即投递|分享职位")


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
    """进入岗位详情页，返回切分后的 JD 区段。"""
    if detail.startswith("http"):
        job_url = detail
    else:
        job_url = base + detail if detail.startswith("#") else base.rstrip("/") + detail
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        _open(page, job_url)
        full = page.inner_text("body")
        browser.close()
    return extract_jd(full)


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

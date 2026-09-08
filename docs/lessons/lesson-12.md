# Lesson 12 · Playwright 浏览器自动化 + 岗位采集实战 ★ 核心技能

> 目标：**掌握** Playwright（而不是"顺手用"），并把岗位采集做成校招虾的正式能力——从公司官网 URL 自动抓岗位列表 + JD，喂给 L11 的简历分析。
> 前置：L1–L11 完成；你已经有 `cli/scrape_jobs.py`（Moka 全链跑通，这是本课最好的起点）。
> 说明：本课把你会但"说不清为什么"的部分系统化（Part A 心智模型），再把脚本升级成正式产出（Part B），最后建立跨平台认知（Part C）。

---

## 0. 本课要解决的问题（为什么需要 Playwright）

校招虾的岗位数据目前来自两个地方：

```
L3 的 CSV 导入  → 一次性、手动，表格里有什么就是什么
腾讯表格(MCP)   → 静态列表，只有公司名和官网 URL，没有 JD
```

但真实世界是：**岗位每天都在变，JD 是网页里 JS 渲染出来的**。你的岗位表格里只有"公司官网 URL"——所以 L12 要让校招虾自己做到：

```
公司官网 URL（你表格里给的）
   ↓ Playwright 打开真浏览器
岗位列表（标题/城市/详情链接）
   ↓ 进入详情页
JD 全文 → 更新 jobs.csv → L11 优化简历用上最新 JD
```

而"打开真浏览器、等渲染完、抓内容"这件事，`requests` 做不到，**Playwright 就是干这个的**。

---

## Part A · Playwright 心智模型（把"会用"变"懂"）

### A1. requests 和 Playwright 的本质区别

| | requests | Playwright |
|---|---|---|
| 拿到什么 | **服务器返回的原始 HTML 字符串** | **一个被真实执行过的浏览器页面** |
| 跑 JS 吗 | ❌ 不跑（JS 是浏览器的事）| ✅ 跑（它就是浏览器）|
| 适合 | 静态页面、API 接口 | JS 渲染的页面（SPA：Vue/React 写的前端）|

**为什么 Moka 必须用 Playwright**：它的岗位列表是前端 JS 动态渲染的——`requests` 拿到的 HTML 里只有一个空壳 div，岗位数据是页面加载后 JS 再填进去的。

> 类比：`requests` 是"看厨房菜单"（拿原始文本）；Playwright 是"派个真人进厨房，等菜炒完端出来"（浏览器帮你把 JS 全部执行完）。

### A2. 对象树（Playwright 唯一重要的心智模型）

所有 Playwright 代码都围绕这棵对象树：

```
sync_playwright()          # ① 入口（with 语句管理生命周期）
  └─ chromium.launch()     # ② 浏览器实例（一个浏览器窗口）
      └─ new_page()        # ③ 页面（一个标签页）
          └─ locator(...)  # ④ 定位器（页面里的"搜索框"）
```

**三条规则**：
1. **只能从上层创建下层**——没有 `playwright` 就没有 `browser`，没有 `browser` 就没有 `page`；
2. **`with sync_playwright() as p:` 退出时自动关闭浏览器**——你 `scrape_jobs.py` 里已经这么写了（第 56 行），这就是为什么每抓一次都 `with` 一次；
3. **`locator` 不是"元素"，是"找元素的方法"**——`page.locator("a")` 是"页面里所有 a 标签的查找器"，真正拿到内容要 `.all()` / `.inner_text()` / `.get_attribute()`。

**为什么 `browser` 和 `page` 要分开**：一个浏览器可以开很多标签页。你要抓列表页 + 详情页，其实可以**共用一个浏览器、开两个 page**——你现在的 `scrape_jobs.py` 是"每次抓都新开浏览器"，简单但慢；以后优化时可以共用一个 `browser`。

### A3. 同步 API vs 异步 API（先知道有这回事）

Playwright 提供两套完全相同的 API：

```python
from playwright.sync_api import sync_playwright     # 同步版（我们现在用）
from playwright.async_api import async_playwright   # 异步版（await 版）
```

- **同步版**：代码从上往下顺序执行，好读、好调试——**脚本和小工具用它**；
- **异步版**：配合 `await`，适合**服务器里高并发**（比如以后校招虾部署成 7×24 服务，同时处理多个抓取任务）。

> 现在只用同步版。知道"还有一套 async"即可——等 L13 部署时如果需要再换。

### A4. 等待策略（抓 SPA 页面 90% 的坑都在这里）

**核心事实**：`page.goto()` 返回 ≠ 页面内容就绪。SPA 是"先给空壳，再慢慢渲染"。所以"等"是必须的，关键是怎么等：

| 方式 | 代码 | 什么时候用 |
|---|---|---|
| 等网络加载 | `goto(url, wait_until="load")` | 兜底第一层（你 `_open` 里已有）|
| 无脑等固定时间 | `page.wait_for_timeout(8000)` | 简单粗暴（你 `_open` 里的 `wait` 参数）|
| **等元素出现**（推荐升级）| `page.locator("a[href*='job']").first.wait_for()` | 等"第一个岗位链接"出现——**等到了才是真渲染完** |

**为什么推荐第 3 种**：固定等 8 秒，网络快时浪费 7 秒，慢时 8 秒可能还不够。等"目标元素出现"才是真正的"就绪"信号。

> 面试点：**抓 SPA 的通用套路 = 渲染 → 抓取 → 文本兜底**：先等元素，再抓，抓不到就 `page.inner_text("body")` 全页文本兜底（你 `scrape_job_detail` 就是这么做的）。

### A5. 选择器（怎么"找到"页面元素）

你现在的做法（`scrape_jobs.py` 第 62 行）：

```python
for a in page.locator("a").all():        # 遍历页面里所有 <a>
    href = a.get_attribute("href") or ""
    if LINK_RE.search(href):             # 正则过滤出"像岗位链接"的
        title, meta = _split_job_text(a.inner_text())
```

**为什么"全量遍历 + 正则过滤"反而是好设计**：你**不知道**这个站点的 DOM 结构，全量遍历 + 过滤 = **不依赖精确结构**，站点改版不崩。这是"通用脚本"该有的姿态。

另外几个常用选择器（以后写"定制脚本"时用）：

```python
page.get_by_text("职位描述")        # 按文本找元素
page.get_by_role("button", name="投递")  # 按角色找（无障碍语义）
page.locator("div.job-item")        # CSS 选择器
```

### A6. 拦截响应（id 藏在 JS 里时的钥匙）★

你之前探索过 zhiye.com：**它的岗位不是 `<a>` 链接，`jobAdId`（UUID）藏在 JS 状态里，DOM 里根本找不到**。这时候"遍历 a 标签"失效，钥匙是**监听网络响应**：

```python
def on_response(resp):
    url = resp.url
    if "/api/jobs" in url and resp.status == 200:   # 找到岗位数据的接口
        data = resp.json()                           # 直接拿 JSON！
        print(data)

page.on("response", on_response)     # 注册监听（页面每次发请求都会回调）
page.goto(url)                       # 触发页面加载 → 页面自己会调那个接口
```

**原理**：页面是 JS 渲染的，那 JS 一定**通过网络接口拿数据**。你拦下这个接口的响应，拿到的是**最干净的结构化数据**（JSON），比从 DOM 抠文本强一万倍。

> 这是"先探再写"的活教材：先在浏览器 DevTools → Network 里看页面调了哪些接口（哪些返回了岗位数据），再写 `page.on("response")` 去拦。**先看真实网络，再写代码。**

---

## Part B · 正式产出：`job_provider_moka.py`（列表 + JD + JSON）

### B1. 先 review 你已有的 `scrape_jobs.py`（逐段"为什么"）

| 你写的 | 为什么这么设计 |
|---|---|
| `LINK_RE = re.compile(r"#/job/\|/job/\|jobAdId=")` | 一个正则兼容多种站点形态（Moka 的 `#/job/{id}`、通用 `/job/`、zhiye 的 `jobAdId=`）——**通用适配的起点** |
| `_open(page, url, wait=8000, retries=3)` | 国内站偶发超时 → 重试 3 次 + 超时 100s + 停顿 3s（网络健壮性标配）|
| `_split_job_text` | 卡片文本里有"急/热/new"等标签行，第一行通常是岗位名——**尽力而为的解析**，容忍脏数据 |
| `browser = p.chromium.launch(channel="msedge", headless=True)` | `channel="msedge"` = 用系统已装的 Edge，**免下载 Chromium**（国内下载超时的救星）；`headless=True` = 无头模式（不弹窗口）|
| `scrape_job_detail` 里 `page.inner_text("body")` | 详情页结构未知 → **全页文本兜底**，再交给下游切分 |

这些都是对的。L12 要做的升级只有两处：**① JD 段落切分 ② 存成 JSON 喂给下游**。

### B2. 两个升级点

**升级点 1：JD 段落切分**——`inner_text("body")` 拿到的是整页文本（导航、页脚全在里面）。用正则把"职位描述"区段标出来：

```python
JD_START = re.compile(r"职位描述|岗位职责|工作职责|岗位要求|任职要求")
JD_END   = re.compile(r"联系方式|简历投递|申请职位|立即投递|分享职位")

def extract_jd(full_text):
    """从整页文本里切出 JD 区段（找不到关键词就整段返回，兜底）。"""
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    start = next((i for i, ln in enumerate(lines) if JD_START.search(ln)), None)
    if start is None:
        return full_text[:2000]              # 没找到关键词：截前 2000 字兜底
    jd = []
    for ln in lines[start:]:
        if JD_END.search(ln) and len(jd) > 1:   # 标题+至少1行正文后才认收尾词（短JD也能正确切）
            break
        jd.append(ln)
    return "\n".join(jd)
```

> 注：初版这里是 `len(jd) > 3`，L14 写测试时被用例抓出短 JD 场景的缺陷（正文不足 3 行时收尾词混入）——**这就是"先测纯逻辑"的价值**。

**升级点 2：结果存 JSON**——列表 + JD 结构化落盘，后续（L13 定时任务、L11 简历分析）都能读：

```python
def save_jobs(jobs, out_path):
    Path(out_path).write_text(
        json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
```

### B3. 完整代码（新建 `cli/job_provider_moka.py`）

```python
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
```

**运行**（你终端，Moka 已验证的 URL）：

```
..\.venv\Scripts\python.exe job_provider_moka.py "https://app.mokahr.com/campus_apply/envisiongroup/43123#/jobs" 0 jobs_out.json
```

### B4. 与 L11 的衔接（JD 进 jobs.csv）

抓到的 JD 要喂给"优化简历"，目前 `jobs.csv` 的 `JD` 列是数据源。**动手任务**：写一个小脚本 `update_jobs_csv.py`，把 `job_provider_moka.py` 抓到的 `{"title", "jd"}` 合并进 `jobs.csv`（公司名/城市保持原样，只更新 `JD` 列），然后发「优化简历 序号」验证用的确实是新 JD。

> 先手动跑通，L13 再变成定时任务——这是"先脚本后服务"原则的又一次实践。

---

## Part C · 跨平台认知：两种适配器（面试亮点）

### C1. 本质区别：岗位 id 在哪

| | Moka 类平台 | zhiye 类平台 |
|---|---|---|
| 岗位 id 在哪 | **DOM 里**（`<a href="#/job/{id}">`）| **JS 状态里**（`jobAdId` 是 UUID，DOM 找不到）|
| 怎么拿列表 | 遍历 `<a>` + 正则过滤（Part B 的做法）| **监听 XHR**（Part A6 的做法）|
| 实现难度 | 低（结构公开）| 高（要猜接口、跟进改版）|

**一句话**：**id 在 DOM → 遍历标签；id 在 JS → 拦截网络**。判断方法：DevTools 里看元素（Elements）里有没有岗位链接——有就 DOM 流，没有就去 Network 找接口。

### C2. 适配器模式（架构 §10.2 JobProvider 的落地）

把"每个平台怎么抓"封装成**接口一致、实现不同**的模块：

```python
# 每个平台一个文件，接口统一：
#   list_jobs(url) -> [{title, meta, detail}]
#   get_job_detail(base, detail) -> str

# job_provider_moka.py —— DOM 流（Part B）
# job_provider_zhiye.py —— XHR 流（Part A6，暂缓）
```

以后 `jobs.csv` 里每个 URL 对应哪个 Provider，由一个"路由"决定（看 URL 域名或页面特征）。**换平台只加文件，不动调用方**——这就是架构文档里 JobProvider 抽象的意义。

### C3. YAGNI 声明（现在不做 zhiye）

- zhiye 适配器**原理已懂、暂不实现**（你在它身上踩过坑：id 是 UUID、要监听 XHR、还可能改版）——**单站点 MVP 跑通即算成功**（大纲风险提示原话）；
- 等 L13/L15 需要多站点时，按 C2 的接口补 `job_provider_zhiye.py` 即可。

---

## 验证清单（做完逐条打勾）

- [ ] `job_provider_moka.py "<Moka URL>"` 抓到列表（标题 + 元信息 + 详情链接）
- [ ] 加序号参数抓到 1 条 JD，且打印的是**切分后的 JD 区段**（不是整页乱文本）
- [ ] 加输出文件参数 → 生成 `jobs_out.json`，打开看结构 `[{title, meta, detail, base, jd}]`
- [ ] （动手任务）`update_jobs_csv.py` 把 JD 合并进 `jobs.csv`，发「优化简历 序号」用的确实是新 JD

## 弄坏再修（必做）

1. **删掉 `channel="msedge"`** 再跑 → 报错要下载 Chromium（国内可能超时）——理解 `msedge` 参数解决的是什么问题；
2. **把 `wait_for_timeout` 改成 0** 再抓列表 → 大概率抓不全——理解"等渲染"为什么必须；
3. **`headless=False`** 跑一次 → 亲眼看到浏览器窗口打开、页面加载、然后被抓取——"它真的在操作浏览器"；
4. 换一个**不是 Moka 的招聘站**试列表 → 大概率"没抓到岗位"，看提示信息理解"适配器"边界。

## 自测题（能口头回答才算过关）

- `requests` 和 Playwright 抓同一个 SPA 页面，结果差在哪？为什么？
- 画出 `playwright → browser → page → locator` 的对象树，说明每层是什么。
- 为什么抓 SPA 必须"等"？`wait_until="load"` 和 `wait_for_timeout(8000)` 和 `locator.wait_for()` 各解决什么？
- Moka 的岗位 id 在哪？zhiye 的在哪？为什么获取方式完全不同？
- 为什么"遍历所有 `<a>` 再正则过滤"比"精确选择器"更稳健？什么时候该用精确选择器？
- `channel="msedge"` 解决什么问题？`headless=True` 是什么？
- 为什么"id 在 DOM 里"和"id 在 JS 里"决定了两种不同的适配器？

---

*做完把 `job_provider_moka.py` + `jobs_out.json` 贴回来，我 review。下一课 L13：部署落地（7×24 常驻）——把校招虾从"你电脑开着才活"变成"永远在线"，顺带把"自动同步岗位"做成定时任务。*

# tests/test_core.py —— 校招虾核心逻辑单元测试（pytest）
#
# 测的都是"纯逻辑"（状态机 / 数据层 / JD 切分 / 合并策略）——
# 不碰网络、不碰飞书、不碰浏览器，任何一个挂了都说明业务规则被改坏。
#
# 跑法（任意目录）：..\.venv\Scripts\python.exe -m pytest tests\ -v

from application_book import ApplicationBook, TRANSITIONS
from job_provider_moka import extract_jd
from sync_jobs import upsert, detail_url


# ============ 状态机 TRANSITIONS（业务规则的"宪法"） ============

def test_first_status_can_move():
    """已投递 必须能走向 笔试/面试/凉凉。"""
    assert "面试" in TRANSITIONS["已投递"]
    assert "笔试" in TRANSITIONS["已投递"]


def test_terminal_states_have_no_exits():
    """三个终态不允许再迁移（终态不可变更）。"""
    for s in ("已接受", "已拒绝", "凉凉"):
        assert TRANSITIONS[s] == [], f"{s} 是终态，不应有出边"


def test_all_targets_are_known_states():
    """所有迁移目标都必须是 TRANSITIONS 里登记过的合法状态。"""
    for outs in TRANSITIONS.values():
        for s in outs:
            assert s in TRANSITIONS, f"迁移目标 {s} 不在状态表里"


# ============ ApplicationBook（tmp_path 隔离，不碰真实数据） ============

def test_add_creates_record_with_initial_status(tmp_path):
    book = ApplicationBook(str(tmp_path / "a.json"))
    book.add("字节", "后端")
    assert book.applications == [
        {"company": "字节", "position": "后端", "status": "已投递"}
    ]


def test_data_persists_across_reload(tmp_path):
    """落盘验证：重新打开同一个文件，数据还在（L2 的核心承诺）。"""
    book = ApplicationBook(str(tmp_path / "a.json"))
    book.add("字节", "后端")
    book2 = ApplicationBook(str(tmp_path / "a.json"))
    assert book2.applications[0]["company"] == "字节"


def test_update_status_legal(tmp_path):
    book = ApplicationBook(str(tmp_path / "a.json"))
    book.add("字节", "后端")
    book.update_status(0, "面试")             # 已投递 → 面试 合法
    assert book.applications[0]["status"] == "面试"


def test_update_illegal_transition_rejected(tmp_path):
    """非法迁移必须被拒绝，且状态保持不变。"""
    book = ApplicationBook(str(tmp_path / "a.json"))
    book.add("字节", "后端")
    book.update_status(0, "Offer")            # 已投递 → Offer 非法
    assert book.applications[0]["status"] == "已投递"


def test_update_terminal_state_rejected(tmp_path):
    book = ApplicationBook(str(tmp_path / "a.json"))
    book.add("字节", "后端")
    book.update_status(0, "凉凉")             # 先到终态
    book.update_status(0, "面试")             # 终态不能再变
    assert book.applications[0]["status"] == "凉凉"


def test_delete_removes_correct_record(tmp_path):
    book = ApplicationBook(str(tmp_path / "a.json"))
    book.add("字节", "后端")
    book.add("腾讯", "前端")
    book.delete(0)
    assert len(book.applications) == 1
    assert book.applications[0]["company"] == "腾讯"   # 删的是第 0 条，剩腾讯


# ============ extract_jd（L12 的 JD 切分管道） ============

def test_extract_jd_keeps_body_cuts_footer():
    page = "网站导航\n关于我们\n职位描述\n1. 负责后端开发\n页脚 联系方式 hr@x.com\n版权所有"
    jd = extract_jd(page)
    assert "负责后端开发" in jd
    assert "hr@x.com" not in jd          # 收尾关键词之后的内容被切掉


def test_extract_jd_fallback_without_keyword():
    """找不到起始关键词 → 兜底返回原文截断（不能崩、不能返回空）。"""
    raw = "没有任何关键词的一个页面文本"
    assert extract_jd(raw) == raw[:2000]


# ============ sync_jobs 的合并策略与 URL 拼接（L13） ============

def test_upsert_updates_existing_row():
    rows = [{"公司": "A", "岗位": "后端", "城市": "", "JD": "旧JD", "链接": "x"}]
    action = upsert(rows, "A", "后端", "新JD", "http://u")
    assert action == "更新"
    assert rows[0]["JD"] == "新JD"
    assert len(rows) == 1                # 不新增行


def test_upsert_adds_new_row():
    rows = []
    action = upsert(rows, "B", "测试工程师", "JD内容", "http://v")
    assert action == "新增"
    assert rows[0] == {"公司": "B", "岗位": "测试工程师", "城市": "",
                       "JD": "JD内容", "链接": "http://v"}


def test_detail_url_hash_form():
    """Moka 形态：detail 是 #/job/xxx → 拼在 base 后。"""
    assert detail_url({"base": "https://x.com", "detail": "#/job/1"}) == \
        "https://x.com#/job/1"


def test_detail_url_absolute_form():
    """detail 本身是完整 URL → 原样返回。"""
    assert detail_url({"detail": "https://y.com/job/2"}) == "https://y.com/job/2"

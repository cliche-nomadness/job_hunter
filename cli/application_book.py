# cli/application_book.py
import json
import os

# 状态机迁移表（从 main.py 搬过来，作为模块级常量）
TRANSITIONS = {
    "已投递": ["笔试", "面试", "凉凉"],
    "笔试":   ["面试", "凉凉"],
    "面试":   ["Offer", "凉凉"],
    "Offer":  ["已接受", "已拒绝"],
    "已接受": [],
    "已拒绝": [],
    "凉凉":   [],
}

class ApplicationBook:
    """投递记录本：数据（applications）+ 操作，全部打包在一起。"""

    def __init__(self, data_file):
        self.data_file = data_file     # 属性：这个账本对应的文件
        self.applications = []         # 属性：记录列表（不再是全局变量！）
        self.load()                    # 创建时自动读文件

    def load(self):
        """从文件读记录。"""
        if os.path.exists(self.data_file):
            with open(self.data_file, "r", encoding="utf-8") as f:
                self.applications = json.load(f)

    def save(self):
        """把记录写回文件。"""
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.applications, f, ensure_ascii=False, indent=2)

    def add(self, company, position):
        """新增一条投递，状态固定"已投递"。"""
        record = {"company": company, "position": position, "status": "已投递"}
        self.applications.append(record)
        self.save()
        print(f"[OK] 已记录 {company} - {position}")

    def list_all(self):
        """打印所有记录。"""
        if len(self.applications) == 0:
            print("（还没有任何投递记录）")
            return
        for i, item in enumerate(self.applications):
            print(f"{i + 1}. {item['company']} - {item['position']} [{item['status']}]")

    def update_status(self, index, new_status):
        """更新第 index 条记录的状态（带状态机校验）。"""
        current = self.applications[index]["status"]
        allowed = TRANSITIONS.get(current, [])
        if len(allowed) == 0:
            print(f"[!] 当前状态是「{current}」，这是终态，不能变更")
            return
        if new_status not in allowed:
            print(f"[!] 不能从「{current}」变成「{new_status}」（允许：{allowed}）")
            return
        self.applications[index]["status"] = new_status
        self.save()
        print("[OK] 已更新")

    def delete(self, index):
        """删除第 index 条记录。"""
        self.applications.pop(index)
        self.save()
        print("[OK] 已删除")
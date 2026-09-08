#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取腾讯文档智能表格（smartsheet）示例
用法：python read_smartsheet.py <access_token>

access_token 获取方式：
  1. 打开 https://docs.qq.com/open 注册开发者并创建应用
  2. 用 client_id / client_secret 走 OAuth 2.0 授权码流程
  3. 把拿到的 access_token 填进来（有效期有限，过期需刷新）

只需 Python 3 标准库，无需安装任何第三方包。
"""

import json
import sys
import urllib.request

MCP_URL = "https://docs.qq.com/openapi/mcp"   # 腾讯文档个人版主 MCP 入口

# ── 从文档 URL 提取的三个关键参数 ────────────────────────────────────────────
# https://docs.qq.com/smartsheet/DRHVEc05MbE5CYUZa?tab=toDOyJ&viewId=vI6O1b
#                                     └─ file_id ─┘   └sheet_id┘ └view_id┘
FILE_ID = "DRHVEc05MbE5CYUZa"
SHEET_ID = "toDOyJ"       # 即 URL 中的 tab 参数，对应工作表「27届内推企业」
VIEW_ID = "vI6O1b"        # 可选，不传则返回该表默认视图数据


def rpc(token: str, tool: str, params: dict) -> dict:
    """调用一次 MCP JSON-RPC 请求"""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",           # MCP 协议固定为 tools/call
        "params": {"name": tool, "arguments": params},
    }).encode("utf-8")

    req = urllib.request.Request(
        MCP_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            # 官方要求：header 的 key 必须是 Authorization，值直接放 token（不带 Bearer）
            # 若返回 401 invalid_token，说明 token 类型不对——必须用 MCP 专用 token，
            # 获取地址：https://docs.qq.com/open/auth/mcp.html（OAuth 应用的 access_token 无效）
            "Authorization": token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "error" in body:
        raise RuntimeError(f"RPC 错误: {body['error']}")
    return body


def parse_tool_result(body: dict) -> dict:
    """MCP 返回的 result.content[0].text 是一段 JSON 字符串，需二次解析"""
    text = body["result"]["content"][0]["text"]
    return json.loads(text)


def flatten_record(record: dict) -> dict:
    """把一条记录的 field_values 列表拍平成 {字段名: 值} 字典"""
    row = {}
    for fv in record.get("field_values", []):
        name = fv["field"]
        if "text_value" in fv:          # 文本字段
            row[name] = "".join(i.get("text", "") for i in fv["text_value"].get("items", []))
        elif "option_value" in fv:      # 单选/多选字段
            row[name] = "、".join(i.get("text", "") for i in fv["option_value"].get("items", []))
        elif "url_value" in fv:         # 超链接字段
            links = [i.get("link", "") for i in fv["url_value"].get("items", [])]
            row[name] = links[0] if links else ""
        else:
            row[name] = json.dumps(fv, ensure_ascii=False)
    return row


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit("请传入 access_token：python read_smartsheet.py <access_token>")
    token = sys.argv[1]

    # 第 1 步（可选）：列出文档下的所有工作表，确认 sheet_id
    tables = parse_tool_result(rpc(token, "smartsheet.list_tables", {"file_id": FILE_ID}))
    if tables.get("error"):
        sys.exit(f"接口返回错误（多为 token 无效或无权限）: {tables['error']}")
    print("== 工作表清单 ==")
    for s in tables["sheets"]:
        print(f'  {s["sheet_id"]:>10}  {s["title"]}')

    # 第 2 步：分页读取记录（limit 最大 100，用 has_more/next 翻页）
    all_rows, offset = [], 0
    while True:
        page = parse_tool_result(rpc(token, "smartsheet.list_records", {
            "file_id": FILE_ID,
            "sheet_id": SHEET_ID,
            "view_id": VIEW_ID,
            "limit": 100,
            "offset": offset,
        }))
        if page.get("error"):
            sys.exit(f"读取记录失败: {page['error']}")
        all_rows.extend(page["records"])
        if not page.get("has_more"):
            break
        offset = page["next"]

    print(f"\n== 共读取 {len(all_rows)} 条记录，示例前 3 条 ==\n")
    for rec in all_rows[:3]:
        print(json.dumps(flatten_record(rec), ensure_ascii=False, indent=2))
        print("-" * 60)


if __name__ == "__main__":
    main()

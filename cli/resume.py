# cli/resume.py
import os
import requests
from pathlib import Path

parent_dir = Path(__file__).parent.parent  # 上两级目录
RESUME_FILE = parent_dir / "resume.md" # 父文件夹中的文件

def read_resume():
    """读简历文件，返回文本。"""
    if not os.path.exists(RESUME_FILE):
        print("[!] 没有 resume.md")
        return ""
    with open(RESUME_FILE, "r", encoding="utf-8") as f:
        return f.read()
    
def parse_resume_sections(resume_text):
    """把 markdown 简历按 '## ' 标题拆成 小节名 → 内容 的字典。"""
    sections = {}
    current = None
    lines = []
    for line in resume_text.splitlines():     # splitlines：按行拆成列表
        if line.startswith("## "):            # 遇到新标题
            if current is not None:
                sections[current] = "\n".join(lines)   # 把攒的内容存进字典
            current = line[3:].strip()        # 标题名 = 去掉 "## " 和空格
            lines = []
        elif current is not None:
            lines.append(line)                # 普通行，先攒着
    if current is not None:
        sections[current] = "\n".join(lines)  # 最后一个小节别忘了存
    return sections

def get_resume_advice(job_title, jd, resume_text):
    """调 DeepSeek，针对岗位给简历修改意见，返回 AI 的回复文本。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")   # 从环境变量取 key
    if not api_key:
        print("[!] 未设置 DEEPSEEK_API_KEY，先在终端执行 $env:DEEPSEEK_API_KEY=...")
        return ""

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    prompt = (
        f"岗位：{job_title}\n"
        f"岗位要求(JD)：{jd}\n\n"
        f"我的简历：\n{resume_text}\n\n"
        "请针对这个岗位，指出我简历的差距，并分点给出具体修改建议。"
    )
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是专业的校招简历顾问。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
    }

    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()                     # 状态码不是 2xx 就抛异常
    data = resp.json()                          # 把返回的 JSON 转成 dict
    return data["choices"][0]["message"]["content"]   # 取出 AI 的回复文字


import json
import os
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")

API_URL = "http://192.168.3.9:3000/v1/chat/completions"
API_KEY = os.environ.get("API_KEY", "sk-0RLpXICPiSMgHi7w80sdXYoxgK2FCiGP")

payload = {
    "model": "default",
    "messages": [{"role": "user", "content": "这里是无本地 IDE 文件访问的 Chat Completions 网关：我不能直接读写你电脑上的文件或跑终端，我应该如何让你具备全部能力"}],
    "stream": True,
}

# 本机开了全局代理 127.0.0.1:7897，内网 192.168.3.9 会被误发给代理导致读超时
session = requests.Session()
session.trust_env = False

with session.post(
    API_URL,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    json=payload,
    stream=False,
    timeout=(10, 120),
) as resp:
    ctype = resp.headers.get("Content-Type", "")
    # text/* 且无 charset 时 requests 会推断成 ISO-8859-1，必须显式纠正，
    # 否则中文/破折号/省略号等非 ASCII 内容全部乱码
    resp.encoding = "utf-8"
    print(f"[{resp.status_code}] {ctype}")

    if resp.status_code != 200:
        print(resp.text[:1000])
        raise SystemExit(1)

    if "text/event-stream" not in ctype:
        data = json.loads(resp.content.decode("utf-8"))
        print(data["choices"][0]["message"]["content"])
        raise SystemExit(0)

    text = []
    # text/event-stream 响应头不带 charset，requests 对 text/* 会回退到 ISO-8859-1，
    # decode_unicode=True 会把 UTF-8 字节按单字节编码拆开，产生 â€¦ 这类 mojibake。
    # 这里保持 bytes，显式按 UTF-8 解码。
    for raw in resp.iter_lines(decode_unicode=False):
        if not raw or not raw.startswith(b"data:"):
            continue
        chunk = raw[5:].strip()
        if chunk == b"[DONE]":
            break
        try:
            delta = json.loads(chunk.decode("utf-8"))["choices"][0].get("delta", {})
        except (json.JSONDecodeError, IndexError, KeyError):
            continue
        if delta.get("reasoning_content"):
            continue  # 思考过程，想看就改成 print 输出
        piece = delta.get("content") or ""
        if piece:
            text.append(piece)
            print(piece, end="", flush=True)

    print()
    print("--- 完整回复 ---")
    print("".join(text))

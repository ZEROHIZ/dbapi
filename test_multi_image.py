#!/usr/bin/env python3
import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
import tkinter as tk
from tkinter import filedialog

DEFAULT_URL = "http://127.0.0.1:5566/v1/images/generations"
DEFAULT_MODEL = "doubao"
DEFAULT_PROMPT = "把多张参考图融合成一张高质量海报，保留主体特征与颜色风格"
DEFAULT_STYLE = "auto"
DEFAULT_RATIO = "1:1"


def ask(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def choose_images() -> list[str]:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_paths = filedialog.askopenfilenames(
        title="请选择 2 到 6 张图片",
        filetypes=[
            ("图片文件", "*.jpg *.jpeg *.png *.webp *.gif *.bmp"),
            ("所有文件", "*.*"),
        ],
    )
    root.destroy()
    return list(file_paths)


def to_data_url(value: str) -> str:
    if value.startswith("http://") or value.startswith("https://") or value.startswith("data:"):
        return value
    if not os.path.isfile(value):
        raise FileNotFoundError(f"图片文件不存在: {value}")
    mime_type, _ = mimetypes.guess_type(value)
    mime_type = mime_type or "application/octet-stream"
    with open(value, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def post_json(url: str, token: str, payload: dict, timeout: int):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=timeout)


def run_non_stream(url: str, token: str, payload: dict, timeout: int):
    start = time.time()
    with post_json(url, token, payload, timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        elapsed = int((time.time() - start) * 1000)
        print(f"\nHTTP {resp.status} in {elapsed}ms\n")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            print(body)
            return

        print(json.dumps(parsed, ensure_ascii=False, indent=2))
        conv_id = parsed.get("id")
        images = []
        try:
            images = parsed["choices"][0]["message"].get("images", [])
        except Exception:
            pass
        print(f"\n结果摘要: id={conv_id!r}, 图片数量={len(images)}")


def run_stream(url: str, token: str, payload: dict, timeout: int):
    start = time.time()
    with post_json(url, token, payload, timeout) as resp:
        print(f"\nHTTP {resp.status} (stream)\n")
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue
            print(line)
            if line == "data: [DONE]":
                break
        elapsed = int((time.time() - start) * 1000)
        print(f"\n流式输出结束，总耗时 {elapsed}ms")


def main():
    print("多图片生成测试")
    print("先填几个参数，然后会弹出文件选择窗口。\n")

    url = ask("接口地址", DEFAULT_URL)
    token = ask("Token（可填 pooled）", "pooled")
    prompt = ask("提示词", DEFAULT_PROMPT)
    style = ask("风格", DEFAULT_STYLE)
    ratio = ask("比例", DEFAULT_RATIO)
    stream = ask("是否流式？(y/n)", "n").lower() == "y"

    print("\n现在会弹出图片选择窗口，请一次选中 2 到 6 张图片。")
    image_paths = choose_images()
    if len(image_paths) < 2:
        print("\n至少要选 2 张图片。")
        input("\n按回车退出...")
        return
    if len(image_paths) > 6:
        image_paths = image_paths[:6]
        print("\n你选了超过 6 张，已自动只取前 6 张。")

    payload = {
        "model": DEFAULT_MODEL,
        "prompt": prompt,
        "style": style,
        "ratio": ratio,
        "stream": stream,
        "auto_delete": False,
        "image": [to_data_url(path) for path in image_paths],
    }

    print("\n已选择文件：")
    for idx, path in enumerate(image_paths, start=1):
        print(f"{idx}. {path}")

    print("\n将发送请求：")
    print(json.dumps({
        "model": payload["model"],
        "prompt": payload["prompt"],
        "style": payload["style"],
        "ratio": payload["ratio"],
        "stream": payload["stream"],
        "image_count": len(payload["image"]),
    }, ensure_ascii=False, indent=2))

    try:
        if stream:
            run_stream(url, token, payload, 600)
        else:
            run_non_stream(url, token, payload, 600)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"\nHTTPError {e.code}: {body}")
    except Exception as e:
        print(f"\n请求失败: {e}")

    input("\n按回车退出...")


if __name__ == "__main__":
    main()

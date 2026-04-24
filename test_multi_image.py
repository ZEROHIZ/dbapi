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
# DEFAULT_URL = "http://192.168.110.30:7000/v1/images/generations"
# DEFAULT_MODEL = "Seedream 4.5"
DEFAULT_MODEL = "Seedream 5.0 Lite"
DEFAULT_PROMPT = """识别以上图片原有实景与全部现有物体，严格保留原本场地、建筑、环境、食物、所有实物元素。**画面必须是空无一人的纯净风光场景，绝对禁止出现任何人物、游客或脸孔。**禁止添加任何原图不存在的物品、建筑、装饰、杂物，不篡改场景结构。
【核心要求：强制打破原构图，进行剧烈环绕位移】
**无论原图原本处于什么视角，机位都必须强制进行大跨度的“环绕式位移”。**必须绕着主体向左前方大幅度平移，并结合极具张力的高低角度变化（如建筑的大透视低角仰拍，或食物/静物的贴近桌面平视及微距特写）。
必须展示出原图视角中完全看不到的另一个侧面。构图必须发生剧烈的破坏与重组，主体的立体感、体积感被极度放大，透视关系必须与原图截然不同（绝对禁止出现与原图相似的构图比例和角度）。
【光影与氛围调整】
**允许根据全新的仰拍视角，适当重构和优化光影效果。**可以调整光线方向，强化明暗对比、增加自然的体积光或环境漫反射，以更好地凸显建筑的几何张力与空间层次。允许对曝光和色彩氛围进行适度美化，使画面更具高级摄影质感，但需符合真实物理规律，保持整体高清写实的风格，避免过度浮夸的失真滤镜感。
**画面干净，绝对禁止出现任何文字、水印、logo。**整体呈现写实高清画质，仅做拍摄机位的剧烈物理空间转换及合理的光影美化。
注：所有生成的图片都需要进行机位的剧烈移动，只要有1张没有移动全部都不合格
我上传几张就生成几张"""
DEFAULT_STYLE = "通用"
DEFAULT_RATIO =""



def ask(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def choose_images() -> list[str]:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_paths = filedialog.askopenfilenames(
        title="请选择 2 到 6 张参考图（图生图）",
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
    print("多图图生图测试 /v1/images/generations")
    print("这是图片生成接口，不是聊天接口。会把多张参考图作为 image 数组发送。\n")

    url = ask("接口地址", DEFAULT_URL)
    token = ask("Token（可填 pooled）", "pooled")
    model = ask("图片模型", DEFAULT_MODEL)
    prompt = ask("图生图提示词", DEFAULT_PROMPT)
    style = ask("风格", DEFAULT_STYLE)
    ratio = ask("比例", DEFAULT_RATIO)
    stream = ask("是否流式？(y/n)", "n").lower() == "y"

    print("\n现在会弹出图片选择窗口，请一次选中 2 到 6 张参考图。")
    image_paths = choose_images()
    if len(image_paths) < 2:
        print("\n至少要选 2 张图片。")
        input("\n按回车退出...")
        return
    if len(image_paths) > 6:
        image_paths = image_paths[:6]
        print("\n你选了超过 6 张，已自动只取前 6 张。")

    payload = {
        "model": model,
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

    print("\n将发送图生图请求：")
    print(json.dumps({
        "url": url,
        "model": payload["model"],
        "prompt": payload["prompt"],
        "style": payload["style"],
        "ratio": payload["ratio"],
        "stream": payload["stream"],
        "image_count": len(payload["image"]),
        "payload_field": "image[]",
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

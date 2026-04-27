#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "http://127.0.0.1:5566"
DEFAULT_MODEL = "Seedream 5.0 Lite"
DEFAULT_PROMPT = "一张未来城市夜景，电影感，高细节，高清写实"


def to_data_url(value: str) -> str:
    if value.startswith(("http://", "https://", "data:")):
        return value
    if not os.path.isfile(value):
        raise FileNotFoundError(f"图片文件不存在: {value}")
    mime_type, _ = mimetypes.guess_type(value)
    mime_type = mime_type or "application/octet-stream"
    with open(value, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def request_json(method: str, url: str, token: str, payload: dict | None = None, timeout: int = 60):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError(f"响应不是 JSON: HTTP {resp.status}\n{body}")


def unwrap_data(response: dict) -> dict:
    if response.get("code") == 0 and isinstance(response.get("data"), dict):
        return response["data"]
    return response


def submit_async_image(args) -> str:
    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "ratio": args.ratio,
        "style": args.style,
    }
    if args.no_auto_delete:
        payload["auto_delete"] = False
    if args.image:
        images = [to_data_url(item) for item in args.image]
        payload["image"] = images[0] if len(images) == 1 else images

    url = args.base_url.rstrip("/") + "/v1/images/generations/async"
    print("提交异步图片任务:")
    print(json.dumps({
        "url": url,
        "model": payload["model"],
        "prompt": payload["prompt"],
        "ratio": payload["ratio"],
        "style": payload["style"],
        "image_count": len(args.image or []),
    }, ensure_ascii=False, indent=2))

    response = request_json("POST", url, args.token, payload, timeout=args.submit_timeout)
    print("\n提交响应:")
    print(json.dumps(response, ensure_ascii=False, indent=2))

    data = unwrap_data(response)
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError("提交响应中没有 task_id")
    return task_id


def poll_task(args, task_id: str) -> dict:
    url = args.base_url.rstrip("/") + f"/v1/generations/tasks/{task_id}"
    deadline = time.time() + args.timeout
    last_status = None

    print(f"\n开始轮询任务: {task_id}")
    while time.time() < deadline:
        response = request_json("GET", url, args.token, timeout=args.query_timeout)
        data = unwrap_data(response)
        status = data.get("status")
        if status != last_status:
            print(f"[{time.strftime('%H:%M:%S')}] status={status}")
            last_status = status

        if status in ("succeeded", "failed"):
            print("\n最终任务响应:")
            print(json.dumps(response, ensure_ascii=False, indent=2))
            return data

        time.sleep(args.interval)

    raise TimeoutError(f"任务 {task_id} 在 {args.timeout}s 内没有完成")


def main():
    parser = argparse.ArgumentParser(description="测试图片异步生成接口，并检查本地保存结果。")
    parser.add_argument("--base-url", default=os.getenv("DOUBAO_API_BASE", DEFAULT_BASE_URL), help="服务地址")
    parser.add_argument("--token", default=os.getenv("DOUBAO_API_TOKEN", "pooled"), help="Authorization token，可填 pooled")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="图片模型")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="提示词")
    parser.add_argument("--ratio", default="1:1", help="图片比例")
    parser.add_argument("--style", default="auto", help="图片风格")
    parser.add_argument("--image", action="append", help="可选参考图，支持本地路径、URL、data URI；可重复传多次")
    parser.add_argument("--no-auto-delete", action="store_true", help="保留豆包会话，不自动删除")
    parser.add_argument("--timeout", type=int, default=360, help="总轮询超时秒数")
    parser.add_argument("--interval", type=int, default=5, help="轮询间隔秒数")
    parser.add_argument("--submit-timeout", type=int, default=60, help="提交请求超时秒数")
    parser.add_argument("--query-timeout", type=int, default=30, help="查询请求超时秒数")
    args = parser.parse_args()

    try:
        task_id = submit_async_image(args)
        task = poll_task(args, task_id)
        if task.get("status") != "succeeded":
            print(f"\n任务失败: {task.get('error')}")
            return 1

        media = task.get("media") or []
        print(f"\n本地文件数量: {len(media)}")
        for idx, item in enumerate(media, start=1):
            print(f"{idx}. {item.get('local_path')} ({item.get('size')} bytes)")

        if not media:
            print("\n任务成功但没有保存到本地文件，请检查生成结果中是否包含图片 URL。")
            return 2
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"\nHTTPError {e.code}: {body}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n测试失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

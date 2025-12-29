import requests
import json
import sys
import time

# 配置
API_BASE = "http://127.0.0.1:8000"
SESSION_ID = "74baaa0b3bc2019b5627b2505fb264f9"  # TODO: 替换为你从豆包获取的 sessionid

def print_separator():
    print("-" * 50 + "\n")

def test_chat():
    print(">>> 1. 正在测试文本对话 (Non-Stream)...")
    url = f"{API_BASE}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {SESSION_ID}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "doubao",
        "messages": [
            {"role": "user", "content": "你好，请自我介绍一下。"}
        ],
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        print(f"HTTP 状态: {response.status_code}")
        data = response.json()
        content = data['choices'][0]['message']['content']
        print(f"回答内容: {content}")
        print_separator()
    except Exception as e:
        print(f"测试失败: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"响应详情: {response.text}")
        print_separator()

def test_stream_chat():
    print(">>> 2. 正在测试文本对话 (Stream)...")
    url = f"{API_BASE}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {SESSION_ID}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "doubao",
        "messages": [
            {"role": "user", "content": "讲个冷笑话。"}
        ],
        "stream": True
    }

    try:
        print("开始接收流式输出:", end="", flush=True)
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    data_str = decoded_line[6:]
                    if data_str.strip() == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        content = data['choices'][0]['delta'].get('content', '')
                        if content:
                            print(content, end="", flush=True)
                    except json.JSONDecodeError:
                        pass
        print("\n\n流式传输结束。")
        print_separator()

    except Exception as e:
        print(f"\n流式测试失败: {e}")
        print_separator()

def test_text_to_image():
    print(">>> 3. 正在测试文生图 (Text-to-Image)...")
    url = f"{API_BASE}/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {SESSION_ID}",
        "Content-Type": "application/json"
    }
    # 参数参考 README 和 源码
    payload = {
        "model": "Seedream 4.0", # 源码默认模型
        "prompt": "一只戴着太阳镜的酷猫，赛博朋克风格",
        "ratio": "1:1",
        "style": "3D",
        "stream": False
    }

    try:
        print("正在请求生成图片 (这可能需要十几秒)...")
        response = requests.post(url, headers=headers, json=payload, timeout=120) # 增加超时时间
        response.raise_for_status()

        data = response.json()
        print(f"HTTP 状态: {response.status_code}")
        
        # 检查返回格式，源码中返回的是 chat.completion 格式
        # 图片 URL 可能在 message.content 中，或者 message.images 数组中 (非标准 OpenAI 字段)
        choice = data.get('choices', [{}])[0]
        message = choice.get('message', {})
        content = message.get('content', '')
        images = message.get('images', [])

        print(f"返回文本: {content}")
        if images:
            print(f"生成的图片 URL ({len(images)}张):")
            for img_url in images:
                print(f" - {img_url}")
        else:
            print("警告: 未在响应中找到 images 字段，请检查 content 是否包含 URL。")
            
        print_separator()
        return images[0] if images else None

    except Exception as e:
        print(f"文生图测试失败: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"响应详情: {response.text}")
        print_separator()
        return None

def test_image_to_image(ref_image_url):
    print(">>> 4. 正在测试图生图 (Image-to-Image)...")
    if not ref_image_url:
        # 使用一个默认的公共图片作为备选
        ref_image_url = "D:\daima\doubao-free-api-master\9dec80e1b813469895b2486c26abc02b~tplv-tb4s082cfz-aigc_resize_mark_1080_1080.webp"
        print(f"使用测试图片 URL: {ref_image_url}")
    else:
        print(f"使用上一轮生成的图片作为参考: {ref_image_url}")

    url = f"{API_BASE}/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {SESSION_ID}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "Seedream 4.0",
        "prompt": "把这只猫变成卡通风格",
        "image": ref_image_url, # 图生图的关键参数
        "ratio": "1:1",
        "style": "卡通",
        "stream": False
    }

    try:
        print("正在请求图生图 (这可能需要十几秒)...")
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        data = response.json()
        print(f"HTTP 状态: {response.status_code}")
        
        choice = data.get('choices', [{}])[0]
        message = choice.get('message', {})
        content = message.get('content', '')
        images = message.get('images', [])

        print(f"返回文本: {content}")
        if images:
            print(f"生成的图片 URL ({len(images)}张):")
            for img_url in images:
                print(f" - {img_url}")
        else:
            print("警告: 未在响应中找到 images 字段。")

        print_separator()

    except Exception as e:
        print(f"图生图测试失败: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"响应详情: {response.text}")
        print_separator()

def test_video_generation():
    print(">>> 5. 正在测试视频生成 (Text-to-Video)...")
    url = f"{API_BASE}/v1/video/generations"
    headers = {
        "Authorization": f"Bearer {SESSION_ID}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": "一只深红色的猫和狗比赛跳水，乌龟突然中途加入,然后在水里面出现一个气球",
        "ratio": "9:16",
        "stream": False
    }

    try:
        print("正在请求生成视频 (这可能需要 1-3 分钟)...")
        response = requests.post(url, headers=headers, json=payload, timeout=300)
        response.raise_for_status()

        data = response.json()
        print(f"HTTP 状态: {response.status_code}")
        
        choice = data.get('choices', [{}])[0]
        message = choice.get('message', {})
        content = message.get('content', '')
        videos = message.get('videos', [])

        print(f"返回文本: {content}")
        if videos:
            print(f"生成的视频信息 ({len(videos)}个):")
            for vid_info in videos:
                print(f" - VID: {vid_info.get('vid')}")
                print(f" - 封面: {vid_info.get('cover')}")
                print(f" - URL: {vid_info.get('url') or '生成中...'}")
        else:
            print("注意: 响应中暂无直接视频链接，可能正在后台生成，请前往官网查看。")
            
        print_separator()
    except Exception as e:
        print(f"视频生成测试失败: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"响应详情: {response.text}")
        print_separator()

def test_image_to_video(ref_image_url=None):
    print(">>> 6. 正在测试图生视频 (Image-to-Video)...")
    if not ref_image_url:
        ref_image_url = "D:\daima\doubao-free-api-master\9dec80e1b813469895b2486c26abc02b~tplv-tb4s082cfz-aigc_resize_mark_1080_1080.webp"
    
    print(f"使用参考图: {ref_image_url}")
    
    # 检查是否为本地文件，如果是则转为 Base64
    import os
    import base64
    import mimetypes
    
    image_input = ref_image_url
    if os.path.exists(ref_image_url):
        print("检测到本地文件，正在转换为 Base64...")
        try:
            mime_type, _ = mimetypes.guess_type(ref_image_url)
            if not mime_type:
                mime_type = "image/png" # 默认
            
            with open(ref_image_url, "rb") as f:
                encoded_string = base64.b64encode(f.read()).decode('utf-8')
                image_input = f"data:{mime_type};base64,{encoded_string}"
            print("转换完成 (Base64)")
        except Exception as e:
            print(f"转换本地文件失败: {e}")
            return

    url = f"{API_BASE}/v1/video/generations"
    headers = {
        "Authorization": f"Bearer {SESSION_ID}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": "让画面中的内容动起来，变成动态视频",
        "ratio": "16:9",
        "image": image_input,
        "stream": False
    }

    try:
        print("正在请求图生视频 (这可能需要 1-3 分钟)...")
        response = requests.post(url, headers=headers, json=payload, timeout=300)
        response.raise_for_status()

        data = response.json()
        print(f"HTTP 状态: {response.status_code}")
        
        choice = data.get('choices', [{}])[0]
        message = choice.get('message', {})
        content = message.get('content', '')
        videos = message.get('videos', [])

        print(f"返回文本: {content}")
        if videos:
            print(f"生成的视频信息 ({len(videos)}个):")
            for vid_info in videos:
                print(f" - VID: {vid_info.get('vid')}")
                print(f" - 封面: {vid_info.get('cover')}")
                print(f" - URL: {vid_info.get('url') or '生成中...'}")
        else:
            print("注意: 响应中暂无直接视频链接，可能正在后台生成，请前往官网查看。")
            
        print_separator()
    except Exception as e:
        print(f"图生视频测试失败: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"响应详情: {response.text}")
        print_separator()

if __name__ == "__main__":
    print("开始运行全功能测试脚本...\n")

    if SESSION_ID == "这里填入你的sessionid":
        print("错误：请先在 test_api.py 中填入你的 SESSION_ID")
        sys.exit(1)

    # 1. 文本对话
    # test_chat()
    
    # 2. 流式对话
    # test_stream_chat()

    # 3. 文生图
    # generated_image_url = test_text_to_image()

    # # 4. 图生图
    # if generated_image_url:
    #     test_image_to_image(generated_image_url)
    
    # 5. 视频生成
    # test_video_generation()
    
    # 6. 图生视频
    test_image_to_video()
    
    print("\n所有测试已完成。")
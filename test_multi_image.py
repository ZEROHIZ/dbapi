import requests
import base64
import os
import time
import json

# API 配置
BASE_URL = "http://127.0.0.1:5566/v1"
HEADERS = {
    "Authorization": "Bearer pooled",
    "Content-Type": "application/json"
}

def encode_image(image_path):
    """处理图片：如果是本地路径则转换为 Base64，如果是 URL 则直接返回"""
    if image_path.startswith(('http://', 'https://')):
        return image_path
    
    if not os.path.exists(image_path):
        print(f"❌ 错误：找不到文件 {image_path}")
        return None
        
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        if image_path.lower().endswith('.png'):
            mime = "image/png"
        elif image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
            mime = "image/jpeg"
        elif image_path.lower().endswith('.webp'):
            mime = "image/webp"
        else:
            mime = "image/octet-stream"
        return f"data:{mime};base64,{encoded_string}"

def mask_base64(obj):
    """递归掩码对象中的 Base64 字符串"""
    if isinstance(obj, str) and (obj.startswith("data:") or len(obj) > 100):
        if "base64," in obj:
            prefix, _ = obj.split("base64,", 1)
            return f"{prefix}base64,[OMITTED,len={len(obj)}]"
        return f"[OMITTED_STRING,len={len(obj)}]"
    elif isinstance(obj, dict):
        return {k: mask_base64(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [mask_base64(i) for i in obj]
    return obj

def print_request(url, payload):
    """打印请求信息（掩码 Base64）"""
    print("\n📤 发送请求:")
    print(f"URL: {url}")
    masked_payload = mask_base64(payload)
    print("Payload:")
    print(json.dumps(masked_payload, indent=2, ensure_ascii=False))

def print_response(response):
    """统一打印响应逻辑"""
    try:
        data = response.json()
        if response.status_code == 200:
            print("✅ 响应成功:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            # 尝试提取图片链接
            if "choices" in data:
                message = data["choices"][0]["message"]
                if "images" in message:
                    print(f"🎨 生成的图片: {message['images']}")
                if "videos" in message:
                    print(f"🎬 生成的视频: {message['videos']}")
        else:
            print(f"❌ 响应失败 (HTTP {response.status_code}):")
            print(json.dumps(data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"⚠️ 无法解析响应 JSON: {e}")
        print(response.text)

def test_multi_image_chat():
    print("\n--- 🧪 测试：多图对话 (Multi-Image Chat) ---")
    print("请输入图片路径或 URL (多个请用逗号分隔):")
    paths_str = input("> ").strip()
    if not paths_str: return
    
    paths = [p.strip().strip('"').strip("'") for p in paths_str.split(',')]
    images = []
    for p in paths:
        img_data = encode_image(p)
        if img_data:
            images.append(img_data)
            
    if not images:
        print("❌ 未提供有效的图片")
        return

    prompt = input("请输入对话提示词 (默认: 描述一下这些图片有什么共同点?): ") or "描述一下这些图片有什么共同点?"

    # 构建 OpenAI 格式的多模态内容
    content = [{"type": "text", "text": prompt}]
    for img in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": img}
        })

    payload = {
        "model": "doubao",
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "stream": False
    }

    try:
        url = f"{BASE_URL}/chat/completions"
        print_request(url, payload)
        print(f"⏳ 正在请求中 (包含 {len(images)} 张图片)...")
        response = requests.post(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        print_response(response)
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        if 'response' in locals(): print(response.text)

def test_multi_image_i2i():
    print("\n--- 🧪 测试：图生图多图模式 (Multi-Image Image-to-Image) ---")
    print("请输入参考图路径或 URL (多个请用逗号分隔):")
    paths_str = input("> ").strip()
    if not paths_str: return
    
    paths = [p.strip().strip('"').strip("'") for p in paths_str.split(',')]
    images = []
    for p in paths:
        img_data = encode_image(p)
        if img_data:
            images.append(img_data)
            
    if not images:
        print("❌ 未提供有效的图片")
        return

    prompt = input("请输入修改提示词 (默认: 融合这几张图片的风格): ") or "融合这几张图片的风格"

    payload = {
        "model": "Seedream 5.0 Lite",
        "prompt": prompt,
        "image": images, # 传列表即为多图模式
        "stream": False
    }

    try:
        url = f"{BASE_URL}/images/generations"
        print_request(url, payload)
        print(f"⏳ 正在请求中 (包含 {len(images)} 张参考图)...")
        response = requests.post(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        print_response(response)
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        if 'response' in locals(): print(response.text)

def main():
    while True:
        print("\n==========================")
        print("Doubao API 多图功能测试")
        print("==========================")
        print("1. 多图对话 (Chat with Multi-Images)")
        print("2. 图生图多图模式 (Multi-Image I2I)")
        print("3. 退出")
        
        choice = input("\n请选择功能 (1-3): ")
        
        if choice == '1':
            test_multi_image_chat()
        elif choice == '2':
            test_multi_image_i2i()
        elif choice == '3':
            print("👋 再见")
            break
        else:
            print("❌ 无效选择")

if __name__ == "__main__":
    main()

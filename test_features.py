import requests
import base64
import os
import time
import json

# API 配置
BASE_URL = "http://127.0.0.1:8000/v1"
HEADERS = {
    "Authorization": "Bearer pooled",
    "Content-Type": "application/json"
}

def encode_image(image_path):
    """将本地图片转换为 Base64 字符串"""
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

def save_result(data, prefix="result"):
    """保存结果链接或 Base64"""
    if not data:
        print("❌ 没有返回数据")
        return

    if 'data' in data and isinstance(data['data'], list):
        item = data['data'][0]
        url = item.get('url')
        b64 = item.get('b64_json')
        
        if url:
            print(f"✅ 生成成功！URL: {url}")
        elif b64:
            filename = f"{prefix}_{int(time.time())}.png"
            with open(filename, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"✅ 生成成功！图片已保存为: {filename}")
    else:
        print("⚠️ 原始返回数据:", json.dumps(data, indent=2, ensure_ascii=False))

def test_text_to_image():
    print("\n--- 🧪 测试：文生图 (Text to Image) ---")
    prompt = input("请输入提示词 (默认: 一只赛博朋克风格的猫): ") or "一只赛博朋克风格的猫"
    
    payload = {
        "model": "Seedream 4.0",
        "ratio": "1:1", 
        "style": "通用",
        "prompt": prompt,
        "stream": False
    }
    
    try:
        print("⏳ 正在请求中...")
        response = requests.post(f"{BASE_URL}/images/generations", headers=HEADERS, json=payload)
        response.raise_for_status()
        save_result(response.json(), "t2i")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        if 'response' in locals(): print(response.text)

def test_image_to_image():
    print("\n--- 🧪 测试：图生图 (Image to Image) ---")
    img_path = input("请输入参考图片路径 (例如 1.jpg): ").strip('"').strip("'")
    if not img_path: return
    
    base64_img = encode_image(img_path)
    if not base64_img: return

    prompt = input("请输入修改提示词 (默认: 变成卡通风格): ") or "变成卡通风格"

    payload = {
        "prompt": prompt,
        "image": base64_img,
        "stream": False
    }

    try:
        print("⏳ 正在请求中...")
        response = requests.post(f"{BASE_URL}/images/generations", headers=HEADERS, json=payload)
        response.raise_for_status()
        save_result(response.json(), "i2i")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        if 'response' in locals(): print(response.text)

def test_image_to_video():
    print("\n--- 🧪 测试：图生视频 (Image to Video) ---")
    img_path = input("请输入首帧图片路径 (例如 1.jpg): ").strip('"').strip("'")
    if not img_path: return
    
    base64_img = encode_image(img_path)
    if not base64_img: return

    prompt = input("请输入视频动态描述 (默认: 镜头缓缓推进): ") or "镜头缓缓推进"

    payload = {
        "prompt": prompt,
        "image": base64_img,
        "stream": False,
        "ratio": "16:9" 
    }

    try:
        print("⏳ 正在请求中（视频生成耗时较长）...")
        response = requests.post(f"{BASE_URL}/video/generations", headers=HEADERS, json=payload)
        response.raise_for_status()
        save_result(response.json(), "i2v")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        if 'response' in locals(): print(response.text)

def main():
    while True:
        print("\n==========================")
        print("Doubao API 功能测试菜单")
        print("==========================")
        print("1. 文生图 (Text -> Image)")
        print("2. 图生图 (Image -> Image)")
        print("3. 图生视频 (Image -> Video)")
        print("4. 退出")
        
        choice = input("\n请选择功能 (1-4): ")
        
        if choice == '1':
            test_text_to_image()
        elif choice == '2':
            test_image_to_image()
        elif choice == '3':
            test_image_to_video()
        elif choice == '4':
            print("👋 再见")
            break
        else:
            print("❌ 无效选择")

if __name__ == "__main__":
    main()
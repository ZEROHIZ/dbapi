import requests
import base64
import os
import time
import json

# ================= 配置区域 =================
# API 地址 (如果是 Docker 部署，请确保端口映射正确)
BASE_URL = "http://127.0.0.1:8000/v1"

# 鉴权方式：使用账号池
HEADERS = {
    "Authorization": "Bearer pooled",
    "Content-Type": "application/json"
}
# ===========================================

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
    """解析并保存结果"""
    if not data:
        print("❌ 没有返回数据")
        return

    # --- 图片测试专用：不提取，直接打印原始 JSON ---
    if prefix in ["t2i", "i2i"]:
        print(f"\n🔍 [DEBUG] 图片接口原始返回数据 ({prefix}):")
        print("-" * 50)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("-" * 50)
        return

    # --- 视频/对话测试：保留原有的解析逻辑 ---
    if 'choices' in data:
        choice = data['choices'][0]
        message = choice.get('message', {})
        content = message.get('content', '')
        
        print("\n📝 返回内容预览:")
        print("-" * 30)
        print(content[:200] + "..." if len(content) > 200 else content)
        print("-" * 30)

        # 检查是否有视频列表
        if 'videos' in message:
            videos = message['videos']
            print(f"\n🎬 获取到 {len(videos)} 个视频:")
            for idx, v in enumerate(videos):
                print(f"  [{idx+1}] 封面: {v.get('cover')}")
                print(f"      链接: {v.get('url')}")
    else:
        # 其他未知格式
        print(f"\n🔍 原始返回数据 ({prefix}):")
        print(json.dumps(data, indent=2, ensure_ascii=False))

# --- 1. 文生图 ---
def test_text_to_image():
    print("\n--- 🎨 1. 文生图 (Text to Image) ---")
    prompt = input("请输入提示词 (默认: 一只赛博朋克风格的猫): ") or "一只赛博朋克风格的猫"
    
    payload = {
        "model": "Seedream 4.0",
        "prompt": prompt,
        "ratio": "1:1",
        "style": "通用",
        "stream": False
    }
    
    run_request("images/generations", payload, "t2i")

# --- 2. 图生图 ---
def test_image_to_image():
    print("\n--- 🖼️ 2. 图生图 (Image to Image) ---")
    img_path = input("请输入参考图片路径 (例如 1.jpg): ").strip('"').strip("'")
    if not img_path: return
    
    base64_img = encode_image(img_path)
    if not base64_img: return

    prompt = input("请输入修改提示词 (默认: 变成卡通风格): ") or "变成卡通风格"

    payload = {
        "model": "Seedream 4.0",
        "prompt": prompt,
        "image": base64_img,
        "ratio": "1:1",
        "style": "通用",
        "stream": False
    }

    run_request("images/generations", payload, "i2i")

# --- 3. 文生视频 ---
def test_text_to_video():
    print("\n--- 🎥 3. 文生视频 (Text to Video) ---")
    prompt = input("请输入视频描述 (默认: 海浪拍打沙滩，夕阳西下): ") or "海浪拍打沙滩，夕阳西下"
    
    payload = {
        "prompt": prompt,
        "ratio": "16:9",
        "stream": False
    }
    
    print("⏳ 视频生成通常需要 1-3 分钟，请耐心等待...")
    run_request("video/generations", payload, "t2v")

# --- 4. 图生视频 ---
def test_image_to_video():
    print("\n--- 🎬 4. 图生视频 (Image to Video) ---")
    img_path = input("请输入首帧图片路径 (例如 1.jpg): ").strip('"').strip("'")
    if not img_path: return
    
    base64_img = encode_image(img_path)
    if not base64_img: return

    prompt = input("请输入动态描述 (默认: 镜头缓慢推进): ") or "镜头缓慢推进"

    payload = {
        "prompt": prompt,
        "image": base64_img,
        "ratio": "16:9",
        "stream": False
    }

    print("⏳ 视频生成通常需要 1-3 分钟，请耐心等待...")
    run_request("video/generations", payload, "i2v")

# --- 通用请求发送 ---
def run_request(endpoint, payload, prefix):
    try:
        print(f"🚀 发送请求到: /{endpoint}")
        start_time = time.time()
        
        response = requests.post(f"{BASE_URL}/{endpoint}", headers=HEADERS, json=payload)
        response.raise_for_status()
        
        duration = time.time() - start_time
        print(f"✅ 请求完成！耗时: {duration:.2f}秒")
        
        save_result(response.json(), prefix)
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP错误: {e}")
        if e.response: print("   服务端返回:", e.response.text)
    except Exception as e:
        print(f"❌ 发生错误: {e}")

def main():
    while True:
        print("\n==========================")
        print("🤖 Doubao API 全功能测试")
        print("==========================")
        print("1. 文生图 (Text -> Image)")
        print("2. 图生图 (Image -> Image)")
        print("3. 文生视频 (Text -> Video)")
        print("4. 图生视频 (Image -> Video)")
        print("5. 退出")
        
        choice = input("\n👉 请选择功能 (1-5): ")
        
        if choice == '1': test_text_to_image()
        elif choice == '2': test_image_to_image()
        elif choice == '3': test_text_to_video()
        elif choice == '4': test_image_to_video()
        elif choice == '5': 
            print("👋 再见")
            break
        else:
            print("❌ 无效选择")

if __name__ == "__main__":
    main()
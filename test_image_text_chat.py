import requests
import base64
import os
import time
import json

# ================= 配置区域 =================
# API 地址
BASE_URL = "http://192.168.110.30:7000/v1"

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

def test_image_text_chat():
    print("\n--- 🖼️💬 图文对话测试 (Image-Text Chat) ---")
    
    # 获取图片输入
    img_input = input("请输入图片路径或 URL (默认使用示例 URL): ").strip('"').strip("'")
    if not img_input:
        # 默认使用一个公开的示例图片 URL
        img_url = "https://p3-dreamina-sign.byteimg.com/tos-cn-i-tb4s082cfz/5326d5d1665145f896a3840e4b15a4de~tplv-tb4s082cfz-aigc_resize:360:360.webp?lk3s=7c3bb0db&x-expires=1775520000&x-signature=HI7bxrfiMlpfarBi%2Fw1km26usl8%3D&format=.webp"
        print(f"ℹ️ 使用默认图片 URL: {img_url}")
    elif img_input.startswith(("http://", "https://")):
        img_url = img_input
    else:
        # 处理本地文件
        base64_img = encode_image(img_input)
        if not base64_img:
            return
        img_url = base64_img

    prompt = input("请输入你想问关于图片的问题 (默认: 这张图片里面有什么？): ") or "这张图片里面有什么？"

    # 构建多模态消息负载
    payload = {
        "model": "doubao",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": img_url
                        }
                    }
                ]
            }
        ],
        "stream": False,
        "auto_delete": False
    }

    try:
        print(f"🚀 发送请求到: /chat/completions")
        start_time = time.time()
        
        response = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload)
        response.raise_for_status()
        
        duration = time.time() - start_time
        print(f"✅ 请求完成！耗时: {duration:.2f}秒")
        
        data = response.json()
        print("\n🔍 接口返回内容:")
        print("-" * 50)
        if 'choices' in data:
            content = data['choices'][0]['message']['content']
            print(content)
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        print("-" * 50)

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP错误: {e}")
        if e.response: 
            print("   服务端状态码:", e.response.status_code)
            print("   服务端返回:", e.response.text)
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    test_image_text_chat()
    input("\n按回车键退出...")

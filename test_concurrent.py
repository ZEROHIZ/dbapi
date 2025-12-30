import requests
import time
import json
import concurrent.futures

# ================= 配置区域 =================
# API 地址
BASE_URL = "http://127.0.0.1:8000/v1" # 请根据实际情况修改 IP

# 鉴权方式：使用账号池 (确保你账号池里至少有 2 个账号)
HEADERS = {
    "Authorization": "Bearer pooled",
    "Content-Type": "application/json"
}
# ===========================================

def run_chat_task():
    """对话测试任务"""
    name = "【对话任务】"
    print(f"🚀 {name} 开始启动...")
    payload = {
        "model": "doubao",
        "messages": [{"role": "user", "content": "你好，请自我介绍一下并告诉我现在的精确时间。"}],
        "stream": False
    }
    try:
        start = time.time()
        response = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload)
        duration = time.time() - start
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            print(f"✅ {name} 耗时: {duration:.2f}s | 返回内容: {content[:50]}...")
        else:
            print(f"❌ {name} 失败: {response.text}")
    except Exception as e:
        print(f"❌ {name} 异常: {e}")

def run_image_task():
    """生图测试任务"""
    name = "【生图任务】"
    print(f"🚀 {name} 开始启动...")
    payload = {
        "model": "Seedream 4.0",
        "prompt": "一只在太空漫步的可爱小猫",
        "ratio": "1:1",
        "style": "通用",
        "stream": False
    }
    try:
        start = time.time()
        response = requests.post(f"{BASE_URL}/images/generations", headers=HEADERS, json=payload)
        duration = time.time() - start
        if response.status_code == 200:
            print(f"✅ {name} 耗时: {duration:.2f}s | 图片已生成，请在控制台确认地址。")
        else:
            print(f"❌ {name} 失败: {response.text}")
    except Exception as e:
        print(f"❌ {name} 异常: {e}")

def run_video_task():
    """生视频测试任务"""
    name = "【视频任务】"
    print(f"🚀 {name} 开始启动...")
    payload = {
        "prompt": "海浪拍打沙滩，夕阳西下，高清，电影感",
        "ratio": "16:9",
        "stream": False
    }
    try:
        start = time.time()
        # 视频生成通常较慢，这里模拟并发启动
        response = requests.post(f"{BASE_URL}/video/generations", headers=HEADERS, json=payload)
        duration = time.time() - start
        if response.status_code == 200:
            print(f"✅ {name} 耗时: {duration:.2f}s | 视频生成请求成功。")
        else:
            print(f"❌ {name} 失败: {response.text}")
    except Exception as e:
        print(f"❌ {name} 异常: {e}")

def main():
    print("=== 🛠️ 开始并发压力与 ID 隔离测试 ===")
    print("提示：请同时观察 API 服务端的控制台日志，确认 DeviceID 是否不同。")
    
    # 使用线程池并发执行 3 个任务
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # 同时提交任务
        futures = [
            executor.submit(run_chat_task),
            executor.submit(run_image_task),
            executor.submit(run_video_task)
        ]
        
        # 等待所有任务完成
        concurrent.futures.wait(futures)

    print("\n=== ✨ 测试执行完毕 ===")

if __name__ == "__main__":
    main()

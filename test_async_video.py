import requests
import time
import json
import sys

# ================= 配置区域 =================
# BASE_URL = "http://127.0.0.1:5566/v1"
# HEADERS = {
#     "Authorization": "Bearer pooled",
#     "Content-Type": "application/json"
# }
# BASE_URL = "http://192.168.110.30:5566/v1/images/generations"
# BASE_URL = "http://192.168.110.30:7000/v1/video/generations"
BASE_URL = "http://192.168.110.30:7000/v1/video"
API_KEY = "sk-VdJ4DV8srDJVKYzbC1eWuokjohrWRfAqu5IQG29jptOoANUj"
# API_KEY ="pooled"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
# ===========================================

def test_async_video_flow():
    print("\n🚀 [1/3] 发送异步视频生成请求...")
    # 请求体，适配 NewAPI 视频生成
    payload = {
        "model": "doubao-video",
        "prompt": "一只在星空下奔跑的赛博朋克风格的小狗",
        "ratio": "16:9",
        # "polling_timeout": 600  # 可选：如果不传，将使用管理后台设置的全局超时
    }
    
    try:
        # 修正：BASE_URL 已经包含 /v1/video，这里只需加 /generations
        response = requests.post(f"{BASE_URL}/generations", headers=HEADERS, json=payload)
        response.raise_for_status()
        task_data = response.json()
        
        # 字段兼容处理
        task_id = task_data.get("task_id") or task_data.get("id")
        print(f"✅ 任务已创建! Task ID: {task_id}")
        print(f"📦 初始状态: {task_data.get('status')}")
        
        if not task_id:
            print("❌ 错误：未获取到 Task ID")
            print(f"服务端完整返回: {json.dumps(task_data, indent=2, ensure_ascii=False)}")
            return

        print(f"\n⏳ [2/3] 开始轮询任务状态 (每 10 秒一次)...")
        start_time = time.time()
        
        while True:
            # 修正：拼接轮询地址
            poll_resp = requests.get(f"{BASE_URL}/generations/{task_id}", headers=HEADERS)
            poll_resp.raise_for_status()
            status_data = poll_resp.json()
            
            status = status_data.get("status")
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed}s] 当前状态: {status}")
            
            if status == "succeeded":
                print("\n🎉 [3/3] 视频生成成功!")
                print(f"🎬 视频 URL: {status_data.get('video', {}).get('url')}")
                break
            elif status == "failed":
                print(f"\n❌ 视频生成失败: {status_data.get('error')}")
                break
            
            if elapsed > 600: # 脚本侧的硬超时保护
                print("\n超时：轮询超过 10 分钟，停止测试。")
                break
                
            time.sleep(10)
            
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"服务端返回: {e.response.text}")

if __name__ == "__main__":
    test_async_video_flow()

import requests

# 你的 NewAPI 地址和 Key
# NEWAPI_URL = "http://192.168.110.30:5566/v1/images/generations"
NEWAPI_URL = "http://127.0.0.1:5566/v1/video/generations"
# API_KEY = "sk-VdJ4DV8srDJVKYzbC1eWuokjohrWRfAqu5IQG29jptOoANUj"
API_KEY ="pooled"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 按照 NewAPI 转换规则构建的数据
# 这里的 extra_body 会被你配置的模板“提权”到根路径
# payload = {
#     "model": "Seedream 4.0",  # 这里传什么不重要，只要在NewAPI里配置了就行
#     "prompt": "一只可爱的赛博朋克风格猫咪",
#     "size": "1:1",
#     "style": "通用" ,
#     "stream": False,
#     "auto_delete": True
# }
payload = {
        "model": "doubao-video",
        "prompt":"猫咪说话人类跪下，然后狗跳起来了",
        "ratio": "16:9",
        "stream": False
    }



try:
    response = requests.post(NEWAPI_URL, headers=headers, json=payload)
    response.raise_for_status()
    print("响应内容:", response.json())
except Exception as e:
    print("请求失败:", e)
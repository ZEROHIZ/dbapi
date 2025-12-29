# API 接口文档

本文档详细说明了对话、绘图、视频生成接口的请求与返回格式。

## 鉴权 (Authentication)

所有接口均需要在 Header 中设置 `Authorization`。

**方式一：指定 SessionID**
```http
Authorization: Bearer [你的sessionid]
```

**方式二：使用账号池 (自动轮询)**
```http
Authorization: Bearer pooled
```

---

## 1. 对话补全 (Chat Completions) 

支持文本对话及图文多模态对话，完全兼容 OpenAI 格式。

**接口地址**: `POST /v1/chat/completions`

### 1.1 纯文本对话

**请求示例**:
```json
{
    "model": "doubao",
    "messages": [
        {
            "role": "user",
            "content": "你好，请自我介绍一下"
        }
    ],
    "stream": false
}
```

### 1.2 图文对话 (多模态)

**请求示例**:
```json
{
  "model": "doubao",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "这张图片里有什么？"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/image.jpg" // 支持 URL 或 Base64
          }
        }
      ]
    }
  ],
  "stream": false
}
```

**响应示例**:
```json
{
    "id": "397193850645250",
    "model": "doubao",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "我叫豆包呀，能陪你聊天、帮你答疑解惑呢。"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "total_tokens": 2
    },
    "created": 1733300587
}
```

---

## 2. 图片生成 (Image Generations)

支持文生图和图生图。

**接口地址**: `POST /v1/images/generations`

### 2.1 文生图 (Text to Image)

**请求示例**:
```json
{
    "model": "Seedream 4.0", // 可选
    "prompt": "一只可爱的赛博朋克风格猫咪",
    "ratio": "1:1", // 比例: 1:1, 16:9, 9:16 等
    "style": "通用", // 风格: 通用, 卡通, 3D 等
    "stream": false
}
```

### 2.2 图生图 (Image to Image)

**请求示例**:
```json
{
    "model": "Seedream 4.0",
    "prompt": "变成卡通风格",
    "image": "https://example.com/original.jpg", // 支持 URL 或 Base64
    "ratio": "1:1",
    "stream": false
}
```

**响应示例**:
```json
{
    "id": "30868724412460802",
    "model": "Seedream 4.0",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "以下是为您生成的图片：\n![image](https://p3-flow-imagex-sign/1.jpg)",
                "images": [
                    "https://p3-flow-imagex-sign/1.jpg"
                ]
            },
            "finish_reason": "stop"
        }
    ],
    "created": 1763985148
}
```

---

## 3. 视频生成 (Video Generations)

支持文生视频和图生视频。

**接口地址**: `POST /v1/video/generations`

### 3.1 文生视频 (Text to Video)

**请求示例**:
```json
{
    "prompt": "海浪拍打沙滩，夕阳西下，镜头缓慢推进",
    "ratio": "16:9", // 默认 16:9
    "stream": false
}
```

### 3.2 图生视频 (Image to Video)

**请求示例**:
```json
{
    "prompt": "让画面动起来，镜头拉远",
    "image": "https://example.com/start_frame.jpg", // 首帧图片 (URL 或 Base64)
    "ratio": "16:9",
    "stream": false
}
```

**响应示例**:
```json
{
    "id": "73568724412460123",
    "model": "doubao-video",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "![视频封面](https://cover-url.jpg)\n视频链接: https://video-url.mp4",
                "videos": [
                    {
                        "vid": "v02834g1...",
                        "cover": "https://cover-url.jpg",
                        "url": "https://video-url.mp4" // 无水印直链
                    }
                ]
            },
            "finish_reason": "stop"
        }
    ],
    "created": 1763985200
}
```

docker run -d --init --name doubao-free-api123 -p 7000:8000 -e ADMIN_PASSWORD=123456 -e SERVER_PORT=8000 -e TZ=Asia/Shanghai -v "${PWD}/data:/app/data" -v "${PWD}/logs:/app/logs" --restart always ghcr.io/zerohiz/dbapi:main
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
    "stream": false,
    "auto_delete": true
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
  "stream": false,
  "auto_delete": false

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
    "created": 1733300587
}
```

### 1.3 工具调用 (Tool Calling)

支持 OpenAI 标准的 `tools` 和 `tool_choice` 参数。

**请求示例**:
```json
{
    "model": "doubao",
    "messages": [
        {
            "role": "user",
            "content": "帮我查一下北京的天气"
        }
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取指定城市的天气状况",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": { "type": "string", "description": "城市名称" }
                    },
                    "required": ["location"]
                }
            }
        }
    ],
    "tool_choice": "auto"
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
    "ratio": "1:1", // size/ratio 比例: 1:1, 16:9, 9:16 等
    "style": "通用", // 风格: 通用, 卡通, 3D 等
    "stream": false,
    "auto_delete": true
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

支持文生视频和图生视频。该接口采用 **异步任务模式**，请求后会立即返回任务 ID，由于视频生成耗时较长（通常 2-10 分钟），您需要根据任务 ID 轮询状态。

### 3.1 创建任务 (Initiate Task)

**接口地址**: `POST /v1/video/generations`

**参数说明**:
- `prompt`: 视频描述词。
- `image`: (可选) 首帧图片 URL 或 Base64。
- `ratio`: (可选) 视频比例，默认 `16:9`。
- `polling_timeout`: (可选) 后台轮询超时时间(秒)，默认使用系统全局设置。

**请求示例**:
```json
{   "model": "doubao-video",
    "prompt": "海浪拍打沙滩，夕阳西下，镜头缓慢推进",
    "ratio": "16:9"
}
```

**响应示例 (立即返回)**:
```json
{
    "task_id": "vtask-7b9b7bd021c411f18e1bb9525c54fdd9",
    "model": "doubao-video",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "视频任务已创建，正在后台生成中。您可以通过任务 ID 查询进度。",
                "task_id": "vtask-7b9b7bd021c411f18e1bb9525c54fdd9"
            },
            "finish_reason": "pending"
        }
    ],
    "created": 1733300587,
    "status": "pending"
}
```

### 3.2 轮询任务状态 (Poll Task Status)

**接口地址**: `GET /v1/video/generations/:id`

**响应示例 (生成中)**:
```json
{
    "task_id": "vtask-7b9b7bd021c411f18e1bb9525c54fdd9",
    "status": "processing",
    "object": "video.generation"
}
```

**响应示例 (成功)**:
```json
{
    "task_id": "vtask-7b9b7bd021c411f18e1bb9525c54fdd9",
    "model": "doubao-video",
    "object": "video.generation",
    "status": "succeeded",
    "created": 1733300587,
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "![视频封面](https://cover-url.jpg)\n视频链接: https://video-url.mp4",
                "videos": [
                    {
                        "vid": "vtask-7b9b7bd0...",
                        "cover": "https://cover-url.jpg",
                        "url": "https://video-url.mp4"
                    }
                ]
            },
            "finish_reason": "stop"
        }
    ]
}
```

---

## 4. 获取可用模型 (List Models)

获取当前系统中所有可用的模型列表，包括文本、视频以及图片生成的具体版本。

**接口地址**: `GET /v1/models`

**响应示例**:
```json
{
  "data": [
    { "id": "doubao", "object": "model", "owned_by": "doubao-free-api" },
    { "id": "doubao-video", "object": "model", "owned_by": "doubao-free-api" },
    { "id": "doubao-image", "object": "model", "owned_by": "doubao-free-api" },
    { "id": "Seedream 4.0", "object": "model", "owned_by": "doubao-free-api" },
    { "id": "Seedream 4.2", "object": "model", "owned_by": "doubao-free-api" },
    { "id": "Seedream 4.5", "object": "model", "owned_by": "doubao-free-api" }
  ]
}
```

**模型选择建议**:
- **图片生成**: 默认使用 `doubao-image` (即 Seedream 4.0)。若需使用新版本，请求时将 `model` 设置为 `Seedream 4.2` 或 `Seedream 4.5` 即可。
- **视频生成**: 默认使用 `doubao-video`。

---

## 5. Session 状态检查 (Token Check)

检查指定的 SessionID (Token) 是否仍然存活（有效）。

**接口地址**: `POST /token/check`

**请求参数**:
- `token`: 需要检查的 SessionID。

**请求示例**:
```json
{
    "token": "your-session-id-here"
}
```

**响应示例**:
```json
{
    "live": true
}
```

---

## 6. 工具与管理 (Utilities)

### 6.1 健康检查 (Ping)
- **地址**: `GET /ping`
- **响应**: `"pong"`

### 6.2 版本查询
- **地址**: `GET /admin/version`
- **响应**: `{"version": "1.0.0"}`

---

## 7. 错误处理 (Error Handling)

当接口返回非 200 状态码时，会返回统一的错误 JSON 格式。

**组件结构**:
- `code`: 系统内部错误码或 API 业务错误码（如 `-2001`）。
- `message`: 详细的错误描述。
- `statusCode`: 建议的 HTTP 状态码。

**响应示例**:
```json
{
    "code": -2001,
    "message": "[请求doubao失败]: 内容安全检测未通过",
    "data": null,
    "statusCode": 500
}
```

> [!TIP]
> 如果您在使用账号池 (`pooled`) 时遇到错误，系统会自动尝试更换账号重试（最多 3 次），直到返回成功或达到重试上限。

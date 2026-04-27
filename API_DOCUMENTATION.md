docker run -d --init --name doubao-free-api123 -p 7000:8000 -e ADMIN_PASSWORD=123456 -e SERVER_PORT=8000 -e TZ=Asia/Shanghai -v "${PWD}/data:/app/data" -v "${PWD}/logs:/app/logs" --restart always ghcr.io/zerohiz/dbapi:2.4
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

支持在单条消息中传入多张图片，所有图片会一次性上传并发送。

**请求示例（多图）**:
```json
{
  "model": "doubao",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "比较这两张图片有什么不同？"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/image1.jpg"
          }
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/image2.jpg"
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

支持单张或多张参考图。`image` 可以是字符串或字符串数组。
如果不指定 `ratio`，将自动根据第一张参考图的尺寸推断最接近的标准比例。

**单图请求示例**:
```json
{
    "model": "Seedream 4.0",
    "prompt": "变成卡通风格",
    "image": "https://example.com/original.jpg",
    "stream": false
}
```

**多图请求示例**:
```json
{
    "model": "Seedream 4.0",
    "prompt": "把两张图片融合成一张",
    "image": [
        "https://example.com/image1.jpg",
        "https://example.com/image2.jpg"
    ],
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
    "stream": false,
    "auto_delete": false
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

---

## 4. 异步图片/视频生成与本地保存

异步接口会立即返回任务 ID，服务端在后台调用原有图片/视频生成逻辑。生成成功后会自动下载结果文件到本地：

- 图片：`data/media/images/`
- 视频：`data/media/videos/`
- 任务记录：`data/media/tasks.json`

原有同步和流式接口保持不变。

### 4.1 异步图片生成

**接口地址**: `POST /v1/images/generations/async`

**请求参数**与 `POST /v1/images/generations` 基本一致，`stream` 会被服务端强制按 `false` 处理。

**请求示例**:
```json
{
  "model": "Seedream 4.0",
  "prompt": "一张未来城市夜景，电影感，高细节",
  "ratio": "16:9",
  "style": "auto",
  "auto_delete": true
}
```

**多图参考请求示例**:
```json
{
    "prompt": "参考多张图片的主体和氛围生成视频，镜头缓慢推进",
    "image": [
        "https://example.com/start_frame_1.jpg",
        "https://example.com/start_frame_2.jpg"
    ],
    "ratio": "16:9",
    "stream": false
}
```

`image` 支持单个字符串或字符串数组，字符串可为 URL 或 Base64 Data URL。

**响应示例**:
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "task_id": "media-1763985200000-a1b2c3d4",
    "status": "queued",
    "query_url": "/v1/generations/tasks/media-1763985200000-a1b2c3d4"
  }
}
```

**异步图生图（单图参考）**:
```json
{
  "model": "Seedream 4.0",
  "prompt": "把这张图改成写实电影海报风格，保留主体结构",
  "image": "https://example.com/original.jpg",
  "ratio": "1:1",
  "style": "auto",
  "auto_delete": true
}
```

**异步图生图（多图参考）**:
```json
{
  "model": "Seedream 4.0",
  "prompt": "融合两张参考图的主体与色彩，生成一张统一风格的新图",
  "image": [
    "https://example.com/reference-1.jpg",
    "https://example.com/reference-2.jpg"
  ],
  "ratio": "16:9",
  "style": "auto",
  "auto_delete": true
}
```

`image` 支持 URL、Base64 Data URL；多图时传字符串数组。

### 4.2 异步视频生成

**接口地址**: `POST /v1/video/generations/async`

**请求参数**与 `POST /v1/video/generations` 基本一致，`stream` 会被服务端强制按 `false` 处理。

**请求示例**:
```json
{
  "model": "doubao-video",
  "prompt": "海浪拍打沙滩，夕阳西下，镜头缓慢推进",
  "ratio": "16:9",
  "auto_delete": false
}
```

**异步图生视频（图片参考模式）**:
```json
{
  "model": "doubao-video",
  "prompt": "让画面动起来，镜头缓慢推进，主体保持清晰",
  "image": "https://example.com/start-frame.jpg",
  "ratio": "16:9",
  "auto_delete": false
}
```

**异步图生视频（多图参考模式）**:
```json
{
  "model": "doubao-video",
  "prompt": "参考多张图片的主体和氛围生成视频，镜头缓慢推进",
  "image": [
    "https://example.com/start-frame-1.jpg",
    "https://example.com/start-frame-2.jpg"
  ],
  "ratio": "16:9",
  "auto_delete": false
}
```

视频的 `image` 支持单个字符串或字符串数组，字符串可为 URL 或 Base64 Data URL。

**响应示例**:
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "task_id": "media-1763985200000-v9x8y7z6",
    "status": "queued",
    "query_url": "/v1/generations/tasks/media-1763985200000-v9x8y7z6"
  }
}
```

### 4.3 查询异步任务

**接口地址**: `GET /v1/generations/tasks/{task_id}`

**状态说明**:
- `queued`: 已创建，等待后台执行
- `running`: 正在生成或下载本地文件
- `succeeded`: 已完成
- `failed`: 失败，查看 `error`

**响应示例**:
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "id": "media-1763985200000-a1b2c3d4",
    "type": "image",
    "status": "succeeded",
    "media": [
      {
        "type": "image",
        "source_url": "https://p3-flow-imagex-sign/1.jpg",
        "local_path": "data/media/images/media-1763985200000-a1b2c3d4-1.jpg",
        "filename": "media-1763985200000-a1b2c3d4-1.jpg",
        "size": 123456,
        "mime_type": "image/jpeg"
      }
    ],
    "created_at": "2026-04-27T10:00:00.000Z",
    "started_at": "2026-04-27T10:00:01.000Z",
    "completed_at": "2026-04-27T10:01:30.000Z"
  }
}
```

### 4.4 清理本地媒体文件

后台 Web 端“危险区域”新增“清理本地媒体文件”按钮，也可以直接调用管理接口。

**接口地址**: `POST /admin/media/clear`

**鉴权**: 需要 `Authorization: Bearer [ADMIN_PASSWORD]`

**说明**: 删除 `data/media/images/`、`data/media/videos/` 下的文件，并清空 `data/media/tasks.json` 任务记录。

---

## 5. 获取可用模型 (List Models)

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

## 6. Session 状态检查 (Token Check)

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

## 7. 工具与管理 (Utilities)

### 7.1 健康检查 (Ping)
- **地址**: `GET /ping`
- **响应**: `"pong"`

### 7.2 版本查询
- **地址**: `GET /admin/version`
- **响应**: `{"version": "2.2"}`

### 7.3 远程重启 (Restart)
- **地址**: `POST /admin/restart`
- **说明**: 远程强制重启服务进程。此操作会延迟 1 秒后执行 `process.exit(0)`，需配合 Docker 的 `--restart always` 或 PM2 等进程守护工具使用。
- **鉴权**: 需在 Header 中设置 `Authorization: Bearer [ADMIN_PASSWORD]`。

**请求示例**:
```http
POST /admin/restart
Authorization: Bearer your_admin_password
```

**响应示例**:
```json
{
    "message": "Restarting service..."
}
```

---

## 8. 错误处理 (Error Handling)

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

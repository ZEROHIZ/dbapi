import axios from "axios";
import AccountManager, { Account } from "@/lib/account-manager.ts";
import Response from "@/lib/response/Response.ts";
import TokenCounter from "@/lib/token-counter.ts";
import { PassThrough } from "stream";
import { createParser } from "eventsource-parser";


class OpenAIProxy {
  /**
   * 转发聊天请求
   */
  public async proxyChat(body: any, account: Account) {
    const { baseUrl, apiKey, modelName } = account;
    const url = `${baseUrl.replace(/\/$/, "")}/chat/completions`;

    const headers: any = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    };

    const data = { ...body };
    if (modelName) data.model = modelName;

    if (body.stream) {
      const response = await axios({
        method: "POST",
        url,
        data,
        headers,
        responseType: "stream",
      });

      // 实时计算流式 Token
      let completionText = "";
      const transStream = new PassThrough();
      const parser = createParser((event) => {
        if (event.type === "event") {
          try {
            const data = JSON.parse(event.data);
            const content = data.choices?.[0]?.delta?.content || "";
            completionText += content;
            if (data.usage) {
               // 如果 API 直接返回了 usage，我们可以使用它（有些 API 会在最后一个 chunk 返回）
               AccountManager.updateAccountUsage(account.id, "chat", data.usage.prompt_tokens, data.usage.completion_tokens);
               TokenCounter.recordUsage(account.id, data.usage.prompt_tokens, data.usage.completion_tokens);
            }
          } catch (e) {}
        }
      });

      response.data.on("data", (chunk: Buffer) => {
        transStream.write(chunk);
        parser.feed(chunk.toString());
      });

      response.data.on("end", () => {
        transStream.end();
        // 如果 API 没有返回 usage，则自行估算
        const promptText = body.messages?.map((m: any) => m.content).join("") || "";
        const promptTokens = TokenCounter.estimateTokens(promptText);
        const completionTokens = TokenCounter.estimateTokens(completionText);
        
        // 注意：这里可能需要防重记录，如果上面 data.usage 已经记录过了
        // 为了简单，我们这里只在没返回 usage 时记录
        AccountManager.updateAccountUsage(account.id, "chat", promptTokens, completionTokens);
        TokenCounter.recordUsage(account.id, promptTokens, completionTokens);
      });

      return new Response(transStream, {
        type: "text/event-stream",
        headers: {
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
      });
    } else {
      const response = await axios.post(url, data, { headers });
      const usage = response.data.usage || {};
      const promptTokens = usage.prompt_tokens || TokenCounter.estimateTokens(body.messages?.map((m: any) => m.content).join("") || "");
      const completionTokens = usage.completion_tokens || TokenCounter.estimateTokens(response.data.choices?.[0]?.message?.content || "");
      
      AccountManager.updateAccountUsage(account.id, "chat", promptTokens, completionTokens);
      TokenCounter.recordUsage(account.id, promptTokens, completionTokens);
      
      return response.data;
    }

  }

  /**
   * 转发图片生成请求
   */
  public async proxyImage(body: any, account: Account) {
    const { baseUrl, apiKey, modelName } = account;
    const url = `${baseUrl.replace(/\/$/, "")}/images/generations`;

    const headers: any = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    };

    const data = { ...body };
    if (modelName) data.model = modelName;

    const response = await axios.post(url, data, { headers });
    
    // 图片目前按次数计费，Token 设为 0
    AccountManager.updateAccountUsage(account.id, "image", 0, 0);
    TokenCounter.recordUsage(account.id, 0, 0);
    
    return response.data;
  }

  /**
   * 转发视频生成请求 (通常也是通过 chat completions 或者专用 endpoint)
   * 这里根据通用 OpenAI 兼容性，如果是专用视频接口可能路径不同，
   * 但实现方案中提到通过 chat completions 模拟，我们这里先支持标准的 /video/generations
   * 如果用户有特殊需求，可以在这里调整
   */
  public async proxyVideo(body: any, account: Account) {
    const { baseUrl, apiKey, modelName } = account;
    // 默认尝试标准路径，如果不存在，可能需要根据具体第三方调整
    const url = `${baseUrl.replace(/\/$/, "")}/video/generations`;

    const headers: any = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    };

    const data = { ...body };
    if (modelName) data.model = modelName;

    const response = await axios.post(url, data, { headers });
    
    // 视频目前按次数计费，Token 设为 0
    AccountManager.updateAccountUsage(account.id, "video", 0, 0);
    TokenCounter.recordUsage(account.id, 0, 0);
    
    return response.data;

  }
}

export default new OpenAIProxy();

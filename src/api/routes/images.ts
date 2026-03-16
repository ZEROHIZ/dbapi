import _ from 'lodash';

import Request from '@/lib/request/Request.ts';
import Response from '@/lib/response/Response.ts';
import images from '@/api/controllers/images.ts';
import openaiProxy from '@/api/controllers/openai-proxy.ts';
import AccountManager from '@/lib/account-manager.ts';


// 定义图片生成请求体的类型（可选，增强类型提示）
interface ImageCompletionRequestBody {
    model: string;
    prompt: string;
    ratio?: string;
    style?: string;
    stream?: boolean;
    n?: number;
    size?: string;
    response_format?: string;
    auto_delete?: boolean;
}

export default {
    // 接口前缀
    prefix: '/v1/images',

    // POST请求路由
    post: {
        /**
         * 文生图生成接口
         * 路径：/v1/images/generations
         * 请求体：{model, prompt, ratio, style, stream}
         */
        '/generations': async (request: Request) => {
            // 1. 扩展参数校验：image为可选字符串（URL/Base64）
            request
                .validate('body.model', _.isString)
                .validate('body.prompt', _.isString)
                .validate('body.ratio', (v) => _.isUndefined(v) || _.isString(v))
                .validate('body.style', (v) => _.isUndefined(v) || _.isString(v))
                .validate('body.stream', _.isBoolean)
                .validate('headers.authorization', _.isString)
                .validate('body.image', (v) => _.isUndefined(v) || _.isString(v)); // 参考图为可选字符串

            // 2. 处理Token
            const authHeader = request.headers.authorization || "";
            let account: any;
            let isPooled = false;

            if (authHeader.includes("pooled") || authHeader.length < 20) {
                isPooled = true;
            } else {
                const tokens = images.tokenSplit(authHeader);
                account = _.sample(tokens) || "";
                if (!account) {
                    throw new Error('无效的Authorization Token');
                }
            }

            // 3. 解构参数：新增image字段
            const {
                model,
                prompt,
                ratio, // Keep ratio for backward compatibility if not using size
                style,
                stream,
                image: referenceImage,
                n, // Added
                size, // Added
                response_format, // Added
                auto_delete // Added
            } = request.body as ImageCompletionRequestBody & { image?: string };

            const autoDelete = _.isBoolean(auto_delete) ? auto_delete : true; // Determine autoDelete value
            let assistantId = model && /^[a-z0-9]{24,}$/.test(model) ? model : undefined;
            if (!assistantId && account) {
                const mapped = AccountManager.getMappedModel(account.id, model);
                if (mapped && /^[a-z0-9]{24,}$/.test(mapped)) {
                    assistantId = mapped;
                }
            }

            // 5. 组装参数：传递参考图 (This block is now partially redundant due to direct passing in createImageCompletion calls)
            const imageParams = {
                model,
                prompt,
                ratio: size || ratio || "1:1", // Prioritize size, then ratio, then default
                style: style || "auto", // Prioritize style, then default
                referenceImage,
                n,
                response_format
            };

            const maxRetries = isPooled ? 3 : 1;
            let attempt = 0;
            let lastError: any;

            while (attempt < maxRetries) {
                attempt++;
                try {
                    if (isPooled) {
                        account = await AccountManager.acquireToken('image', model);
                    }
                    if (isPooled && account.type === 'openai') {
                        return await openaiProxy.proxyImage(request.body, account);
                    }

                    if (stream) {
                        const s = await images.createImageCompletionStream({
                            model,
                            prompt,
                            ratio: size || ratio || "1:1",
                            style: style || "auto",
                            referenceImage
                        }, account, assistantId, 0, autoDelete);
                        if (isPooled) {
                            const token = account.token;
                            s.on('end', () => AccountManager.releaseToken(token));
                            s.on('error', () => AccountManager.releaseToken(token));
                        }
                        return new Response(s, {
                            type: "text/event-stream",
                            headers: {
                                "Cache-Control": "no-cache, no-transform",
                                "Connection": "keep-alive",
                                "X-Accel-Buffering": "no"
                            }
                        });
                    } else {
                        const result = await images.createImageCompletion({
                            model,
                            prompt,
                            ratio: size || ratio || "1:1",
                            style: style || "auto",
                            referenceImage
                        }, account, assistantId, 0, autoDelete);
                        if (isPooled) AccountManager.releaseToken(account.token);
                        return result;
                    }
                } catch (err: any) {
                    lastError = err;
                    if (isPooled && account) {
                        const statusCode = err.errcode || err.status || err.statusCode || err.response?.status;
                        let policyAction = 'error';
                        if (statusCode) {
                            policyAction = AccountManager.applyResponsePolicy(account.id, statusCode);
                        }
                        AccountManager.releaseToken(account.token);

                        if (policyAction === 'retry' && attempt < maxRetries) {
                            // TypeScript doesn't know logger here natively without import, but logger is imported at top
                            const l = require('@/lib/logger.ts').default;
                            l.warn(`[API] 策略触发重图试 (第 ${attempt}/${maxRetries} 次): ${statusCode}.`);
                            continue;
                        }
                    }
                    throw err;
                }
            }
            throw lastError;
        }
    }
};

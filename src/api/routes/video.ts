import _ from 'lodash';

import Request from '@/lib/request/Request.ts';
import Response from '@/lib/response/Response.ts';
import video from '@/api/controllers/video.ts';
import openaiProxy from '@/api/controllers/openai-proxy.ts';
import AccountManager from '@/lib/account-manager.ts';


interface VideoCompletionRequestBody {
    prompt: string;
    ratio?: string;
    model?: string;
    image?: string;
    stream: boolean;
    auto_delete?: boolean;
}

export default {
    prefix: '/v1/video',

    post: {
        /**
         * 视频生成接口
         * 路径：/v1/video/generations
         */
        '/generations': async (request: Request) => {
            request
                .validate('body.prompt', _.isString)
                .validate('body.ratio', (v) => _.isUndefined(v) || _.isString(v))
                .validate('body.model', (v) => _.isUndefined(v) || _.isString(v))
                .validate('body.image', (v) => _.isUndefined(v) || _.isString(v))
                .validate('body.stream', _.isBoolean)
                .validate('headers.authorization', _.isString);

            const authHeader = request.headers.authorization || "";
            let account: any;
            let isPooled = false;

            if (authHeader.includes("pooled") || authHeader.length < 20) {
                isPooled = true;
            } else {
                const tokens = video.tokenSplit(authHeader);
                account = _.sample(tokens) || "";
                if (!account) {
                    throw new Error('无效的Authorization Token');
                }
            }

            const {
                prompt,
                ratio,
                model,
                stream,
                image,
                auto_delete
            } = request.body as VideoCompletionRequestBody;
            const autoDelete = _.isBoolean(auto_delete) ? auto_delete : false;

            let assistantId = model && /^[a-z0-9]{24,}$/.test(model) ? model : undefined;
            if (!assistantId && account) {
                const mapped = AccountManager.getMappedModel(account.id, model);
                if (mapped && /^[a-z0-9]{24,}$/.test(mapped)) {
                    assistantId = mapped;
                }
            }

            const videoParams = {
                prompt,
                ratio: ratio || "16:9",
                model,
                image
            };

            let maxRetries = isPooled ? 3 : 1;
            let attempt = 0;
            let lastError: any;

            while (attempt < maxRetries) {
                attempt++;
                try {
                    if (isPooled) {
                        account = await AccountManager.acquireToken('video', model);
                    }
                    if (isPooled && account.type === 'openai') {
                        return await openaiProxy.proxyVideo(request.body, account);
                    }

                    if (stream) {

                        const s = await video.createVideoCompletionStream(videoParams, account, assistantId, 0, autoDelete);
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
                        const result = await video.createVideoCompletion(videoParams, account, assistantId, 0, autoDelete);
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
                            const l = require('@/lib/logger.ts').default;
                            l.warn(`[API] 策略触发重试视频 (第 ${attempt}/${maxRetries} 次): ${statusCode}.`);
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

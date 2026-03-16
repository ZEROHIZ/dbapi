import _ from 'lodash';

import Request from '@/lib/request/Request.ts';
import Response from '@/lib/response/Response.ts';
import chat from '@/api/controllers/chat.ts';
import openaiProxy from '@/api/controllers/openai-proxy.ts';
import logger from '@/lib/logger.ts';
import AccountManager from '@/lib/account-manager.ts';


export default {

    prefix: '/v1/chat',

    post: {

        '/completions': async (request: Request) => {
            request
                .validate('body.conversation_id', v => _.isUndefined(v) || _.isString(v))
                .validate('body.messages', _.isArray)
                .validate('headers.authorization', _.isString)
            
            const authHeader = request.headers.authorization || "";
            let account: any;
            let isPooled = false;

            // 如果 Authorization 为 Bearer pooled 或者没有提供有效的 sessionid，则使用账号池
            if (authHeader.includes("pooled") || authHeader.length < 20) {
                isPooled = true;
            } else {
                // refresh_token切分
                const tokens = chat.tokenSplit(authHeader);
                // 随机挑选一个refresh_token
                account = _.sample(tokens) || "";
            }

            const {model, conversation_id: convId, messages, stream, tools, auto_delete} = request.body;
            const autoDelete = _.isBoolean(auto_delete) ? auto_delete : true;
            let assistantId = model && /^[a-z0-9]{24,}$/.test(model) ? model : undefined;
            if (!assistantId && account) {
                const mapped = AccountManager.getMappedModel(account.id, model);
                if (mapped && /^[a-z0-9]{24,}$/.test(mapped)) {
                    assistantId = mapped;
                }
            }

            const maxRetries = isPooled ? 3 : 1;
            let attempt = 0;
            let lastError: any;

            while (attempt < maxRetries) {
                attempt++;
                try {
                    if (isPooled) {
                        // Re-acquire token for each attempt if pooled
                        account = await AccountManager.acquireToken('chat', model);
                    }
                    
                    if (isPooled && account.type === 'openai') {
                        return await openaiProxy.proxyChat(request.body, account);
                    }

                    if (stream) {
                        const s = await chat.createCompletionStream(messages, account, assistantId, convId, 0, tools, autoDelete, model);
                        
                        // 如果是池化账号，在流结束时释放
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
                        const res = await chat.createCompletion(messages, account, assistantId, convId, 0, tools, autoDelete, model);
                        if (isPooled) AccountManager.releaseToken(account.token);
                        return res;
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
                            logger.warn(`[API] 策略触发重试 (第 ${attempt}/${maxRetries} 次): ${statusCode}.`);
                            continue;
                        }
                    }
                    throw err;
                }
            }
            throw lastError;
        }

    }

}
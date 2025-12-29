import _ from 'lodash';

import Request from '@/lib/request/Request.ts';
import Response from '@/lib/response/Response.ts';
import chat from '@/api/controllers/chat.ts';
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
            let token: string;
            let isPooled = false;

            // 如果 Authorization 为 Bearer pooled 或者没有提供有效的 sessionid，则使用账号池
            if (authHeader.includes("pooled") || authHeader.length < 20) {
                token = await AccountManager.acquireToken();
                isPooled = true;
            } else {
                // refresh_token切分
                const tokens = chat.tokenSplit(authHeader);
                // 随机挑选一个refresh_token
                token = _.sample(tokens) || "";
            }

            const {model, conversation_id: convId, messages, stream} = request.body;
            const assistantId = /^[a-z0-9]{24,}$/.test(model) ? model : undefined

            try {
                if (stream) {
                    const s = await chat.createCompletionStream(messages, token, assistantId, convId);
                    
                    // 如果是池化账号，在流结束时释放
                    if (isPooled) {
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
                    const res = await chat.createCompletion(messages, token, assistantId, convId);
                    if (isPooled) AccountManager.releaseToken(token);
                    return res;
                }
            } catch (err) {
                if (isPooled) AccountManager.releaseToken(token);
                throw err;
            }
        }

    }

}
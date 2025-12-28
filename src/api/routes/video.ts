import _ from 'lodash';

import Request from '@/lib/request/Request.ts';
import Response from '@/lib/response/Response.ts';
import video from '@/api/controllers/video.ts';

interface VideoCompletionRequestBody {
    prompt: string;
    ratio?: string; // e.g., "16:9", "9:16", "1:1"
    model?: string;
    stream: boolean;
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
                .validate('body.stream', _.isBoolean)
                .validate('headers.authorization', _.isString);

            const tokens = video.tokenSplit(request.headers.authorization);
            const token = _.sample(tokens);
            if (!token) {
                throw new Error('无效的Authorization Token');
            }

            const {
                prompt,
                ratio,
                model,
                stream
            } = request.body as VideoCompletionRequestBody;

            const assistantId = model && /^[a-z0-9]{24,}$/.test(model) ? model : undefined;

            const videoParams = {
                prompt,
                ratio: ratio || "16:9",
                model
            };

            if (stream) {
                const s = await video.createVideoCompletionStream(videoParams, token, assistantId);
                return new Response(s, {
                    type: "text/event-stream",
                    headers: {
                        "Cache-Control": "no-cache, no-transform",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no"
                    }
                });
            } else {
                const result = await video.createVideoCompletion(videoParams, token, assistantId);
                return new Response(result);
            }
        }
    }
};

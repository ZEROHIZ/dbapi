import _ from 'lodash';

import Request from '@/lib/request/Request.ts';
import Response from '@/lib/response/Response.ts';
import video from '@/api/controllers/video.ts';
import openaiProxy from '@/api/controllers/openai-proxy.ts';
import AccountManager from '@/lib/account-manager.ts';
import APIException from '@/lib/exceptions/APIException.ts';
import FailureBody from '@/lib/response/FailureBody.ts';
import EX from '@/api/consts/exceptions.ts';


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
         * 视频生成接口 (异步创建)
         * 路径：/v1/video/generations
         */
        '/generations': async (request: Request) => {
            request
                .validate('body.prompt', _.isString)
                .validate('body.ratio', (v) => _.isUndefined(v) || _.isString(v))
                .validate('body.model', (v) => _.isUndefined(v) || _.isString(v))
                .validate('body.image', (v) => _.isUndefined(v) || _.isString(v))
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
                image,
                auto_delete,
                timeout
            } = request.body as any;
            const autoDelete = _.isBoolean(auto_delete) ? auto_delete : false;

            // 读取超时设置 (秒转毫秒)
            const pollingTimeout = (Number(timeout) || Number(request.headers['x-polling-timeout']) || 600) * 1000;

            const VideoTaskManager = require('@/lib/video-task-manager.ts').default;
            const task = VideoTaskManager.addTask(model || "doubao-video");

            // 后台处理逻辑
            (async () => {
                try {
                    if (isPooled) {
                        account = await AccountManager.acquireToken('video', model);
                        account.isPooled = true;
                    }

                    const videoParams = {
                        prompt,
                        ratio: ratio || "16:9",
                        model,
                        image,
                        taskId: task.id,
                        polling_timeout: pollingTimeout
                    };

                    await video.createVideoCompletion(videoParams, account, undefined, 0, autoDelete);
                    // Token 的释放已在控制器后台逻辑中处理
                } catch (err: any) {
                    const l = require('@/lib/logger.ts').default;
                    l.error(`[Video-Route] 异步任务启动失败: ${err.message}`);
                    VideoTaskManager.updateTask(task.id, {
                        status: 'failed',
                        error: { code: 'start_failed', message: err.message }
                    });
                    if (isPooled && account) AccountManager.releaseToken(account.token);
                }
            })();

            // 立即返回任务信息
            return new Response({
                id: task.id,
                model: task.model,
                status: task.status,
                created_at: task.created_at
            });
        }
    },

    get: {
        /**
         * 获取视频生成任务状态
         * 路径：/v1/video/generations/:id
         */
        '/generations/:id': async (request: Request) => {
            const id = request.params.id;
            const VideoTaskManager = require('@/lib/video-task-manager.ts').default;
            const task = VideoTaskManager.getTask(id);

            if (!task) {
                throw new APIException(EX.API_REQUEST_FAILED, '未找到指定的任务');
            }

            return new Response(task);
        }
    }
};

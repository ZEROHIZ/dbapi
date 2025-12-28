import {PassThrough} from "stream";
import crypto from "crypto";
import path from "path";
import _ from "lodash";
import mime from "mime";
import axios, {AxiosRequestConfig, AxiosResponse} from "axios";

import APIException from "@/lib/exceptions/APIException.ts";
import EX from "@/api/consts/exceptions.ts";
import {createParser} from "eventsource-parser";
import logger from "@/lib/logger.ts";
import util from "@/lib/util.ts";
import { logRequest } from "@/lib/debug-logger.ts";

// 模型名称
const MODEL_NAME = "doubao-video";
// 默认的AgentID (视频可能使用不同的ID，暂时复用或使用通用ID)
const DEFAULT_ASSISTANT_ID = "497858"; 
// 版本号
const VERSION_CODE = "20800";
// PC版本
const PC_VERSION = "2.44.0";
// 设备ID
const DEVICE_ID = `7${util.generateRandomString({length: 18, charset: "numeric"})}`;
// WebID
const WEB_ID = `7${util.generateRandomString({length: 18, charset: "numeric"})}`;
// 最大重试次数
const MAX_RETRY_COUNT = 3;
// 重试延迟
const RETRY_DELAY = 5000;
// 伪装headers
const FAKE_HEADERS = {
    Accept: "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-control": "no-cache",
    "Last-event-id": "undefined",
    Origin: "https://www.doubao.com",
    Pragma: "no-cache",
    Priority: "u=1, i",
    Referer: "https://www.doubao.com",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
};

/**
 * 获取缓存中的access_token
 */
async function acquireToken(refreshToken: string): Promise<string> {
    return refreshToken;
}

/**
 * 生成伪msToken
 */
function generateFakeMsToken() {
    const bytes = crypto.randomBytes(96);
    return bytes
        .toString("base64")
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=/g, "");
}

/**
 * 生成伪a_bogus
 */
function generateFakeABogus() {
    return `mf-${util.generateRandomString({
        length: 34,
    })}-${util.generateRandomString({
        length: 6,
    })}`;
}

/**
 * 生成cookie
 */
function generateCookie(refreshToken: string) {
    return [
        `sessionid=${refreshToken}`,
        `sessionid_ss=${refreshToken}`,
    ].join("; ");
}

/**
 * 请求doubao
 */
async function request(method: string, uri: string, refreshToken: string, options: AxiosRequestConfig = {}) {
    const token = await acquireToken(refreshToken);
    const requestConfig: AxiosRequestConfig = {
        method,
        url: `https://www.doubao.com${uri}`,
        params: {
            aid: DEFAULT_ASSISTANT_ID,
            device_id: DEVICE_ID,
            device_platform: "web",
            language: "zh",
            pc_version: PC_VERSION,
            pkg_type: "release_version",
            real_aid: DEFAULT_ASSISTANT_ID,
            region: "CN",
            samantha_web: 1,
            sys_region: "CN",
            tea_uuid: WEB_ID,
            "use-olympus-account": 1,
            version_code: VERSION_CODE,
            web_id: WEB_ID,
            web_tab_id: util.uuid(),
            ...(options.params || {})
        },
        headers: {
            ...FAKE_HEADERS,
            Cookie: generateCookie(token),
            "X-Flow-Trace": `04-${util.uuid()}-${util.uuid().substring(0, 16)}-01`,
            ...(options.headers || {})
        },
        timeout: 15000,
        validateStatus: () => true,
        ..._.omit(options, "params", "headers"),
    };

    logRequest(requestConfig.method || method, requestConfig.url || uri, requestConfig.params, requestConfig.headers, requestConfig.data);

    const response = await axios.request(requestConfig);
    if (options.responseType == "stream")
        return response;
    return checkResult(response);
}

/**
 * 移除会话
 */
async function removeConversation(
    convId: string,
    refreshToken: string
) {
    try {
        const params = {
            msToken: generateFakeMsToken(),
            a_bogus: generateFakeABogus()
        };
        const headers = {
            Referer: `https://www.doubao.com/chat/${convId}`,
            "Agw-js-conv": "str",
            "Sec-Ch-Ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"'
        };
        await request("POST", "/samantha/thread/delete", refreshToken, {
            data: { conversation_id: convId },
            params,
            headers
        });
        logger.success(`会话 ${convId} 删除成功`);
    } catch (err) {
        logger.error(`删除会话 ${convId} 失败:`, err);
    }
}

/**
 * 获取视频播放地址
 * @param videoId 视频ID
 */
async function getVideoPlayInfo(videoId: string, refreshToken: string) {
    try {
        const res: any = await request("GET", "/samantha/video/get_play_info", refreshToken, {
            params: {
                video_id: videoId
            }
        });
        // 假设返回结构中包含 play_url_list 或类似字段
        // 根据抓包 @2.md，这里需要仔细处理
        if (res && res.play_url_list && res.play_url_list.length > 0) {
            return res.play_url_list[0].url; // 优先取第一个 URL
        }
        return null;
    } catch (e) {
        logger.error(`获取视频播放信息失败 [${videoId}]:`, e);
        return null;
    }
}


/**
 * 同步视频生成
 * @param params { prompt, ratio, model }
 */
async function createVideoCompletion(
    videoParams: { prompt: string; ratio: string; model?: string },
    refreshToken: string,
    assistantId = DEFAULT_ASSISTANT_ID,
    retryCount = 0
) {
    return (async () => {
        const { prompt, ratio, model } = videoParams;
        logger.info(`收到视频生成请求：prompt=${prompt}, ratio=${ratio}`);

        // 构造 content 为 JSON 字符串
        const contentJson = JSON.stringify({
            text: prompt,
            ratio: ratio || "16:9", // 默认 16:9
            // model 字段视情况添加，如果服务端支持
        });

        const videoMessage = [
            {
                content: contentJson,
                content_type: 2020, // 视频生成类型
                attachments: [],
            },
        ];

        const response = await request("post", "/samantha/chat/completion", refreshToken, {
            data: {
                messages: videoMessage,
                completion_option: {
                    is_regen: false,
                    with_suggest: false,
                    need_create_conversation: true,
                    launch_stage: 1,
                    is_replace: false,
                    is_delete: false,
                    message_from: 0,
                    action_bar_skill_id: 17, // 根据抓包 @7.md，video 可能是 17
                    use_auto_cot: false,
                    resend_for_regen: false,
                    enable_commerce_credit: false,
                    event_id: "0"
                },
                evaluate_option: { web_ab_params: "" },
                conversation_id: "0",
                local_conversation_id: `local_${util.generateRandomString({ length: 16, charset: "numeric" })}`,
                local_message_id: util.uuid()
            },
            headers: {
                Referer: "https://www.doubao.com/chat/",
                "agw-js-conv": "str, str",
            },
            timeout: 300000,
            responseType: "stream"
        });

        const contentType = response.headers["content-type"] || "";
        if (contentType.indexOf("text/event-stream") === -1) {
            response.data.on("data", (buffer: any) => logger.error(buffer.toString()));
            throw new APIException(
                EX.API_REQUEST_FAILED,
                `Stream response Content-Type invalid: ${contentType}`
            );
        }

        const streamStartTime = util.timestamp();
        // 复用 receiveStream 逻辑，但需要适配视频
        const answer = await receiveStream(response.data);
        logger.success(
            `视频生成流传输完成 ${util.timestamp() - streamStartTime}ms`
        );

        /* 调试阶段暂时不删除会话
        removeConversation(answer.id, refreshToken).catch(
            (err) => console.error('移除视频生成会话失败：', err)
        );
        */

        return answer;
    })().catch((err) => {
        if (retryCount < MAX_RETRY_COUNT) {
            logger.error(`视频生成流响应错误: ${err.stack}`);
            logger.warn(`${RETRY_DELAY / 1000}秒后重试...`);
            return (async () => {
                await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY));
                return createVideoCompletion(
                    videoParams,
                    refreshToken,
                    assistantId,
                    retryCount + 1
                );
            })();
        }
        throw err;
    });
}

/**
 * 流式视频生成
 */
async function createVideoCompletionStream(
    videoParams: { prompt: string; ratio: string; model?: string },
    refreshToken: string,
    assistantId = DEFAULT_ASSISTANT_ID,
    retryCount = 0
) {
    return (async () => {
        const { prompt, ratio, model } = videoParams;
        logger.info(`收到流式视频生成请求：prompt=${prompt}, ratio=${ratio}`);

        const contentJson = JSON.stringify({
            text: prompt,
            ratio: ratio || "16:9",
        });

        const videoMessage = [
            {
                content: contentJson,
                content_type: 2020,
                attachments: [],
            },
        ];

        const response = await request("post", "/samantha/chat/completion", refreshToken, {
            data: {
                messages: videoMessage,
                completion_option: {
                    is_regen: false,
                    with_suggest: false,
                    need_create_conversation: true,
                    launch_stage: 1,
                    is_replace: false,
                    is_delete: false,
                    message_from: 0,
                    action_bar_skill_id: 17,
                    use_auto_cot: false,
                    resend_for_regen: false,
                    enable_commerce_credit: false,
                    event_id: "0"
                },
                evaluate_option: { web_ab_params: "" },
                conversation_id: "0",
                local_conversation_id: `local_${util.generateRandomString({ length: 16, charset: "numeric" })}`,
                local_message_id: util.uuid()
            },
            headers: {
                Referer: "https://www.doubao.com/chat/",
                "agw-js-conv": "str, str",
            },
            timeout: 300000,
            responseType: "stream"
        });

        const contentType = response.headers["content-type"] || "";
        if (contentType.indexOf("text/event-stream") === -1) {
            logger.error(`无效的响应Content-Type: ${contentType}`);
            response.data.on("data", (buffer: any) => logger.error(buffer.toString()));
            const transStream = new PassThrough();
            transStream.end(
                `data: ${JSON.stringify({
                    id: "",
                    model: MODEL_NAME,
                    object: "video.completion.chunk",
                    choices: [
                        {
                            index: 0,
                            delta: { content: "服务暂时不可用，第三方响应错误" },
                            finish_reason: "stop",
                        },
                    ],
                    created: util.unixTimestamp(),
                })}

`
            );
            return transStream;
        }

        const streamStartTime = util.timestamp();
        return createTransStream(response.data, (convId: string) => {
            logger.success(
                `流式视频生成传输完成 ${util.timestamp() - streamStartTime}ms`
            );
            /* 调试阶段暂时不删除会话
            removeConversation(convId, refreshToken).catch(
                (err) => console.error(err)
            );
            */
        });
    })().catch((err) => {
        if (retryCount < MAX_RETRY_COUNT) {
            logger.error(`流式视频生成响应错误: ${err.stack}`);
            logger.warn(`${RETRY_DELAY / 1000}秒后重试...`);
            return (async () => {
                await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY));
                return createVideoCompletionStream(
                    videoParams,
                    refreshToken,
                    assistantId,
                    retryCount + 1
                );
            })();
        }
        throw err;
    });
}

function checkResult(result: AxiosResponse) {
    if (!result.data) return null;
    const { code, msg, data } = result.data;
    if (!_.isFinite(code)) return result.data;
    if (code === 0) return data;
    throw new APIException(EX.API_REQUEST_FAILED, `[请求doubao失败]: ${msg}`);
}

/**
 * 从流接收完整的消息内容
 */
async function receiveStream(stream: any): Promise<any> {
    let temp = Buffer.from('');
    // 存储视频结果
    const videos: Array<{ vid?: string; cover?: string; url?: string }> = [];
    const emittedKeys = new Set<string>();

    return new Promise((resolve, reject) => {
        const data = {
            id: "",
            model: MODEL_NAME,
            object: "chat.completion",
            choices: [
                {
                    index: 0,
                    message: {
                        role: "assistant",
                        content: "",
                        videos: [] as any[]
                    },
                    finish_reason: "stop",
                },
            ],
            usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
            created: util.unixTimestamp(),
        };
        let isEnd = false;
        const finalize = () => {
            data.choices[0].message.content = data.choices[0].message.content.replace(/\n$/, "");
            // 将收集到的视频信息放入 content 或 extra 字段
            if (videos.length > 0) {
                data.choices[0].message.videos = videos;
                const md = videos.map((v, i) => {
                    return `![视频封面${i + 1}](${v.cover})
视频链接: ${v.url || "生成中(请稍后查看)"}`;
                }).join("\n\n");
                data.choices[0].message.content += (data.choices[0].message.content ? "\n\n" : "") + md;
            }
        };

        const parser = createParser((event) => {
            try {
                if (event.type !== "event" || isEnd) return;
                const rawResult = _.attempt(() => JSON.parse(event.data));
                if (_.isError(rawResult)) return;
                
                if (rawResult.code)
                    throw new APIException(EX.API_REQUEST_FAILED, `[请求doubao失败]: ${rawResult.code}-${rawResult.message}`);
                
                if (rawResult.event_type == 2003) {
                    isEnd = true;
                    finalize();
                    return resolve(data);
                }
                
                // 监听 2001 (常规消息) 和可能出现的 2074 (生成内容)
                if (rawResult.event_type != 2001) return;

                const result = _.attempt(() => JSON.parse(rawResult.event_data));
                if (_.isError(result)) return;

                if (result.is_finish) {
                    isEnd = true;
                    finalize();
                    return resolve(data);
                }
                if (!data.id && result.conversation_id)
                    data.id = result.conversation_id;

                const message = result.message;
                if (!message || !message.content) return;

                // 尝试解析文本内容
                let text = "";
                const parsed = _.attempt(() => JSON.parse(message.content));
                if (!_.isError(parsed)) {
                    if (typeof parsed === "string") text = parsed;
                    else if (typeof parsed.text === "string") text = parsed.text;
                    else if (parsed.delta && typeof parsed.delta.text === "string") text = parsed.delta.text;
                    else if (typeof parsed.content === "string") text = parsed.content;
                } else if (typeof message.content === "string") {
                    text = message.content;
                }
                if (text) data.choices[0].message.content += text;

                // 重点：检查 content_type 是否包含视频信息 (通常是 2074)
                const ctype = message.content_type;
                if (ctype === 2074) {
                    const payload = _.isError(parsed) ? _.attempt(() => JSON.parse(message.content)) : parsed;
                    if (!_.isError(payload) && payload && Array.isArray(payload.creations)) {
                        payload.creations.forEach((c: any) => {
                            // 检查视频字段
                            const vidObj = c?.video;
                            if (vidObj) {
                                const vid = vidObj.vid;
                                const cover = vidObj.video_cover?.url;
                                const url = vidObj.video_url; // 有时直接有url
                                if (vid && !emittedKeys.has(vid)) {
                                    emittedKeys.add(vid);
                                    videos.push({ vid, cover, url });
                                }
                            }
                        });
                    }
                }
            } catch (err) {
                logger.error(err);
                reject(err);
            }
        });

        stream.on("data", (buffer: any) => {
            if (buffer.toString().indexOf('') !== -1) {
                temp = Buffer.concat([temp, buffer]);
                return;
            }
            if (temp.length > 0) {
                buffer = Buffer.concat([temp, buffer]);
                temp = Buffer.from('');
            }
            parser.feed(buffer.toString());
        });
        stream.once("error", (err: any) => reject(err));
        stream.once("close", () => {
            finalize();
            resolve(data);
        });
    });
}

/**
 * 创建转换流 (SSE)
 */
function createTransStream(stream: any, endCallback?: Function) {
    let convId = "";
    let temp = Buffer.from('');
    const created = util.unixTimestamp();
    const emittedKeys = new Set<string>();
    const transStream = new PassThrough();

    // 初始包
    !transStream.closed && transStream.write(
        `data: ${JSON.stringify({
            id: convId,
            model: MODEL_NAME,
            object: "chat.completion.chunk",
            choices: [{ index: 0, delta: { role: "assistant", content: "" }, finish_reason: null }],
            created,
        })}

`
    );

    const parser = createParser((event) => {
        try {
            if (event.type !== "event") return;
            const rawResult = _.attempt(() => JSON.parse(event.data));
            if (_.isError(rawResult)) return;

            if (rawResult.event_type == 2003) {
                 transStream.write(`data: ${JSON.stringify({
                    id: convId,
                    model: MODEL_NAME,
                    object: "chat.completion.chunk",
                    choices: [{ index: 0, delta: { role: "assistant", content: "" }, finish_reason: "stop" }],
                    created,
                })}

`);
                !transStream.closed && transStream.end("data: [DONE]\n\n");
                endCallback && endCallback(convId);
                return;
            }

            if (rawResult.event_type != 2001) return;

            const result = _.attempt(() => JSON.parse(rawResult.event_data));
            if (_.isError(result)) return;

            if (!convId) convId = result.conversation_id;
            
            if (result.is_finish) {
                transStream.write(`data: ${JSON.stringify({
                    id: convId,
                    model: MODEL_NAME,
                    object: "chat.completion.chunk",
                    choices: [{ index: 0, delta: { role: "assistant", content: "" }, finish_reason: "stop" }],
                    created,
                })}

`);
                !transStream.closed && transStream.end("data: [DONE]\n\n");
                endCallback && endCallback(convId);
                return;
            }

            const message = result.message;
            if (!message || !message.content) return;

            // 解析内容
            const content = _.attempt(() => JSON.parse(message.content));
            
            // 检查视频生成信息
            if (message.content_type === 2074 && !_.isError(content)) {
                const creations = Array.isArray((content as any).creations) ? (content as any).creations : [];
                for (const c of creations) {
                    const vidObj = c?.video;
                    if (vidObj) {
                        const vid = vidObj.vid;
                        const cover = vidObj.video_cover?.url;
                        const url = vidObj.video_url; // 如果直接有
                        if (vid && !emittedKeys.has(vid)) {
                            emittedKeys.add(vid);
                            const md = `![视频封面](${cover})
视频链接: ${url || `(ID: ${vid})`}
`;
                            transStream.write(`data: ${JSON.stringify({
                                id: convId,
                                model: MODEL_NAME,
                                object: "chat.completion.chunk",
                                choices: [{ index: 0, delta: { role: "assistant", content: md }, finish_reason: null }],
                                created,
                            })}

`);
                        }
                    }
                }
            }

            // 解析文本
            let text = "";
            if (!_.isError(content)) {
                if (typeof content === "string") text = content;
                else if (typeof (content as any).text === "string") text = (content as any).text;
                else if ((content as any).delta && typeof (content as any).delta.text === "string") text = (content as any).delta.text;
                else if (typeof (content as any).content === "string") text = (content as any).content;
            } else if (typeof message.content === "string") {
                text = message.content;
            }

            if (text) {
                transStream.write(`data: ${JSON.stringify({
                    id: convId,
                    model: MODEL_NAME,
                    object: "chat.completion.chunk",
                    choices: [{ index: 0, delta: { role: "assistant", content: text }, finish_reason: null }],
                    created,
                })}

`);
            }

        } catch (err) {
            logger.error(err);
            !transStream.closed && transStream.end("\n\n");
        }
    });

    stream.on("data", (buffer: any) => {
         if (buffer.toString().indexOf('') !== -1) {
            temp = Buffer.concat([temp, buffer]);
            return;
        }
        if (temp.length > 0) {
            buffer = Buffer.concat([temp, buffer]);
            temp = Buffer.from('');
        }
        parser.feed(buffer.toString());
    });
    stream.once("error", () => !transStream.closed && transStream.end("data: [DONE]\n\n"));
    stream.once("close", () => !transStream.closed && transStream.end("data: [DONE]\n\n"));
    return transStream;
}

/**
 * Token切分
 */
function tokenSplit(authorization: string) {
    return authorization.replace("Bearer ", "").split(",");
}

export default {
    createVideoCompletion,
    createVideoCompletionStream,
    tokenSplit,
};

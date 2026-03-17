import fs from 'fs-extra';
import path from 'path';
import _ from 'lodash';
import util from './util.ts';
import logger from './logger.ts';

export interface VideoTask {
    id: string;
    task_id: string; // 增加 task_id 字段用于兼容
    model: string;
    status: 'pending' | 'processing' | 'succeeded' | 'failed';
    created_at: number;
    progress?: number;
    video?: {
        url: string;
    };
    error?: {
        code: string;
        message: string;
    };
}

class VideoTaskManager {
    private tasks: Map<string, VideoTask> = new Map();
    private readonly filePath: string;

    constructor() {
        this.filePath = path.resolve(process.cwd(), 'data', 'video-tasks.json');
        this.loadTasks();
    }

    private loadTasks() {
        try {
            if (fs.existsSync(this.filePath)) {
                const data = fs.readJsonSync(this.filePath);
                if (Array.isArray(data)) {
                    data.forEach(task => {
                        this.tasks.set(task.id, task);
                    });
                }
            }
        } catch (err) {
            logger.error(`[VideoTaskManager] 加载任务失败: ${err.message}`);
        }
    }

    private saveTasks() {
        try {
            const data = Array.from(this.tasks.values());
            // 只保留最近的 1000 个任务，避免文件过大
            const recentTasks = _.sortBy(data, 'created_at').reverse().slice(0, 1000);
            fs.ensureDirSync(path.dirname(this.filePath));
            fs.writeJsonSync(this.filePath, recentTasks, { spaces: 2 });
        } catch (err) {
            logger.error(`[VideoTaskManager] 保存任务失败: ${err.message}`);
        }
    }

    public addTask(model: string): VideoTask {
        const id = `vtask-${util.uuid(false)}`;
        const task: VideoTask = {
            id,
            task_id: id,
            model,
            status: 'pending',
            created_at: util.unixTimestamp()
        };
        this.tasks.set(id, task);
        this.saveTasks();
        return task;
    }

    public getTask(id: string): VideoTask | undefined {
        return this.tasks.get(id);
    }

    public updateTask(id: string, updates: Partial<VideoTask>) {
        const task = this.tasks.get(id);
        if (task) {
            Object.assign(task, updates);
            this.saveTasks();
        }
    }
}

export default new VideoTaskManager();

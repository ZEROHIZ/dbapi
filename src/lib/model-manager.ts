import fs from "fs-extra";
import path from "path";
import logger from "./logger.ts";

const DATA_DIR = path.join(process.cwd(), "data");
const MODELS_FILE = path.join(DATA_DIR, "models.json");

export interface ModelConfig {
    id: string;
    object: "model";
    owned_by: string;
    backendModel?: string; // 默认对应的上游模型名称
    type: "chat" | "image" | "video";
    defaultParams?: Record<string, any>;
    enabled: boolean;
}

class ModelManager {
    private models: ModelConfig[] = [];

    constructor() {
        this.loadModels();
    }

    private async loadModels() {
        try {
            if (await fs.pathExists(MODELS_FILE)) {
                this.models = await fs.readJson(MODELS_FILE);
            } else {
                // 初始化默认模型
                this.models = [
                    { id: "doubao", object: "model", owned_by: "doubao-free-api", type: "chat", enabled: true },
                    { id: "doubao-image", object: "model", owned_by: "doubao-free-api", backendModel: "Seedream 4.0", type: "image", enabled: true },
                    { id: "doubao-video", object: "model", owned_by: "doubao-free-api", type: "video", enabled: true },
                    { id: "Seedream 4.0", object: "model", owned_by: "doubao-free-api", backendModel: "Seedream 4.0", type: "image", enabled: true },
                    { id: "Seedream 4.2", object: "model", owned_by: "doubao-free-api", backendModel: "Seedream 4.2", type: "image", enabled: true },
                    { id: "Seedream 4.5", object: "model", owned_by: "doubao-free-api", backendModel: "Seedream 4.5", type: "image", enabled: true }
                ];
                await this.saveModels();
            }
        } catch (e) {
            logger.error("加载模型配置文件失败:", e);
        }
    }

    public async saveModels() {
        try {
            await fs.writeJson(MODELS_FILE, this.models, { spaces: 2 });
        } catch (e) {
            logger.error("保存模型配置文件失败:", e);
        }
    }

    public getEnabledModels() {
        return this.models.filter(m => m.enabled);
    }

    public getAllModels() {
        return this.models;
    }

    public getModelConfig(modelId: string) {
        return this.models.find(m => m.id === modelId);
    }

    public async addModel(config: ModelConfig) {
        this.models.push(config);
        await this.saveModels();
    }

    public async updateModel(id: string, updates: Partial<ModelConfig>) {
        const index = this.models.findIndex(m => m.id === id);
        if (index !== -1) {
            this.models[index] = { ...this.models[index], ...updates };
            await this.saveModels();
            return true;
        }
        return false;
    }

    public async addOrUpdateModel(config: ModelConfig, mergeProviders: boolean = true) {
        const index = this.models.findIndex(m => m.id === config.id);
        if (index !== -1) {
            const existing = this.models[index];
            let newOwnedBy = config.owned_by;
            
            if (mergeProviders && config.owned_by) {
                // 合并策略：如果新配置有 owned_by，则将其添加到现有别名列表中（去重）
                const providers = [
                    ...(existing.owned_by || "").split(/[,，/]/).map(p => p.trim()),
                    ...config.owned_by.split(/[,，/]/).map(p => p.trim())
                ].filter(p => p.length > 0);
                newOwnedBy = [...new Set(providers)].join(', ');
            }

            // 更新除 id 之外的字段，owned_by 采用合并后的值（或覆盖后的值）
            this.models[index] = { 
                ...existing, 
                ...config, 
                owned_by: newOwnedBy 
            };
        } else {
            this.models.push(config);
        }
        await this.saveModels();
    }

    public async deleteModel(id: string) {
        this.models = this.models.filter(m => m.id !== id);
        await this.saveModels();
    }
}

export default new ModelManager();

import fs from "fs-extra";
import path from "path";
import util from "@/lib/util.ts";
import logger from "@/lib/logger.ts";
import cron from "cron";
import axios from "axios";
import { EventEmitter } from "events";
import ResponsePolicyManager, { PolicyAction } from "./response-policy.ts";


const DATA_DIR = path.join(process.cwd(), "data");
const ACCOUNTS_FILE = path.join(DATA_DIR, "accounts.json");
const SETTINGS_FILE = path.join(DATA_DIR, "settings.json");

export enum AccountStatus {
  IDLE = "idle",
  BUSY = "busy",
  COOLDOWN = "cooldown"
}

export type AccountType = "doubao" | "openai";
export type AccountCapability = "chat" | "image" | "video";


export interface Account {
  id: string;
  token: string;
  name: string;
  enabled: boolean;
  
  // 类型与权重
  type: AccountType;
  weight: number;

  // 第三方 OpenAI 兼容 API 字段
  baseUrl?: string;
  apiKey?: string;
  capability?: AccountCapability;
  modelName?: string;

  // 设备信息指纹
  deviceId?: string;
  webId?: string;
  userId?: string;

  // 统计与限制
  limitChat: number;  // -1 表示不限
  limitImage: number;
  limitVideo: number;
  
  usageChat: number;
  usageImage: number;
  usageVideo: number;
  
  totalUsage: number; // 总调用次数
  
  // Token 用量统计
  totalPromptTokens: number;
  totalCompletionTokens: number;

  // 运行时状态
  status?: AccountStatus;
  lastUsed?: number;
  cooldownUntil?: number;   // 状态码策略导致的长冷却
  cooldownReason?: string;
  
  // 健康检查
  lastHealthCheck?: number;
  healthStatus?: "healthy" | "unhealthy";
  healthError?: string;
  skipHealthCheck?: boolean; // 新增：是否跳过健康检查

  // 兼容旧字段（读取时转换，保存时废弃）
  dailyLimit?: number;
  dailyUsage?: number;
}


export interface Settings {
  cooldownTime: number; // 毫秒
  defaultModel: string;
  enableHealthCheck?: boolean; // 新增：是否开启全局健康检查
}

export type RequestType = "chat" | "image" | "video";

class AccountManager extends EventEmitter {
  private accounts: Account[] = [];
  private lastRoundRobinIndex: number = -1; // 用于轮询
  private settings: Settings = {
    cooldownTime: 10000,
    defaultModel: "doubao-lite-4k",
  };

  
  // 队列需要记录请求类型
  private queue: Array<{ 
      type: RequestType;
      resolve: (token: string) => void; 
      reject: (err: any) => void 
  }> = [];

  constructor() {
    super();
    this.init();
  }

  private async init() {
    await fs.ensureDir(DATA_DIR);
    await this.loadAccounts();
    await this.loadSettings();

    // 每天0点重置
    new cron.CronJob("0 0 0 * * *", () => {
      this.resetDailyUsage();
    }).start();

    // 账号健康检查：每 30 分钟一次
    new cron.CronJob('0 */30 * * * *', () => {
        if (this.settings.enableHealthCheck !== false) {
            this.checkAllAccountsHealth();
        }
    }, null, true);

    logger.success("[AccountManager] 初始化完成，已开启定时任务");

    // 初始化运行时状态
    this.accounts.forEach(acc => {
      acc.status = AccountStatus.IDLE;
    });
    
    logger.info(`[AccountManager] 系统初始化完成，共加载 ${this.accounts.length} 个账号。`);
  }

  private async loadAccounts() {
    try {
      if (await fs.pathExists(ACCOUNTS_FILE)) {
        const stored = await fs.readJson(ACCOUNTS_FILE);
        this.accounts = stored.map((s: any) => ({
            ...s,
            status: AccountStatus.IDLE,
            type: s.type || "doubao",
            weight: s.weight || 1,
            baseUrl: s.baseUrl || "",
            apiKey: s.apiKey || "",
            capability: s.capability || undefined,
            modelName: s.modelName || "",
            totalPromptTokens: s.totalPromptTokens || 0,
            totalCompletionTokens: s.totalCompletionTokens || 0,
            cooldownUntil: s.cooldownUntil || 0,
            cooldownReason: s.cooldownReason || "",
            // 兼容逻辑：如果没有新字段，使用默认值
            limitChat: s.limitChat !== undefined ? s.limitChat : -1,
            limitImage: s.limitImage !== undefined ? s.limitImage : 60,
            limitVideo: s.limitVideo !== undefined ? s.limitVideo : 0,
            usageChat: s.usageChat || 0,
            usageImage: s.usageImage || 0,
            usageVideo: s.usageVideo || 0,
            totalUsage: s.totalUsage || 0
        }));
      }
    } catch (e) {
      logger.error("加载账号文件失败:", e);
    }
  }

  private async saveAccounts() {
    try {
      // 仅保存必要字段，清理旧字段
      const toSave = this.accounts.map(a => ({
        id: a.id, token: a.token, name: a.name, enabled: a.enabled,
        type: a.type, weight: a.weight,
        baseUrl: a.baseUrl, apiKey: a.apiKey, capability: a.capability, modelName: a.modelName,
        deviceId: a.deviceId, webId: a.webId, userId: a.userId,
        limitChat: a.limitChat, limitImage: a.limitImage, limitVideo: a.limitVideo,
        usageChat: a.usageChat, usageImage: a.usageImage, usageVideo: a.usageVideo,
        totalUsage: a.totalUsage,
        totalPromptTokens: a.totalPromptTokens,
        totalCompletionTokens: a.totalCompletionTokens,
        cooldownUntil: a.cooldownUntil,
        cooldownReason: a.cooldownReason
      }));

      await fs.writeJson(ACCOUNTS_FILE, toSave, { spaces: 2 });
    } catch (e) {
      logger.error("保存账号文件失败:", e);
    }
  }

  private async loadSettings() {
    try {
      if (await fs.pathExists(SETTINGS_FILE)) {
        this.settings = await fs.readJson(SETTINGS_FILE);
      }
    } catch (e) {
      logger.error("加载设置失败:", e);
    }
  }

  public async saveSettings(newSettings: Partial<Settings>) {
    this.settings = { ...this.settings, ...newSettings };
    try {
      await fs.writeJson(SETTINGS_FILE, this.settings, { spaces: 2 });
    } catch (e) {
      logger.error("保存设置失败:", e);
    }
  }

  // 计算某类服务的总剩余额度 (如果是无限则返回一个极大值)
  public getTotalRemainingUsage(type: RequestType = 'chat'): number {
      return this.accounts
          .filter(a => a.enabled)
          .reduce((sum, a) => {
              if (type === 'chat') return a.limitChat === -1 ? sum + 999999 : sum + Math.max(0, a.limitChat - a.usageChat);
              if (type === 'image') return sum + Math.max(0, a.limitImage - a.usageImage);
              if (type === 'video') return sum + Math.max(0, a.limitVideo - a.usageVideo);
              return sum;
          }, 0);
  }

  private tryGetAvailableAccount(type: RequestType): Account | null {
    const total = this.accounts.length;
    if (total === 0) return null;

    const now = Date.now();
    
    // 从上次索引的下一个开始循环
    for (let i = 1; i <= total; i++) {
        const index = (this.lastRoundRobinIndex + i) % total;
        const a = this.accounts[index];

        if (!a.enabled) continue;
        
        // 检查状态码策略导致的冷却
        if (a.cooldownUntil && a.cooldownUntil > now) continue;

        // 检查运行时状态 (BUSY/COOLDOWN)
        if (a.status !== AccountStatus.IDLE) continue;

        // 检查第三方渠道功能匹配
        if (a.type === 'openai') {
           if (a.capability && a.capability !== type) continue;
        }
        
        // 检查对应额度
        if (type === 'chat' && a.limitChat !== -1 && a.usageChat >= a.limitChat) continue;
        if (type === 'image' && a.usageImage >= a.limitImage) continue;
        if (type === 'video' && a.usageVideo >= a.limitVideo) continue;
        
        this.lastRoundRobinIndex = index;
        return a;
    }

    return null;
  }


  public acquireToken(type: RequestType = 'chat'): Promise<Account> {
    return new Promise((resolve, reject) => {
      const remaining = this.getTotalRemainingUsage(type);
      
      // 简单流控：如果剩余为0，拒绝
      // 注意：对于chat如果是-1，remaining会很大
      if (remaining <= 0) {
          return reject(new Error(`系统今日 [${type}] 额度已耗尽。`));
      }

      const account = this.tryGetAvailableAccount(type);
      if (account) {
        this.lockAccount(account, type);
        resolve(account);
      } else {
        // 进入队列
        this.queue.push({ type, resolve: (tokenOrAccount: any) => resolve(tokenOrAccount), reject });
        logger.info(`[AccountManager] 暂无空闲账号，请求 [${type}] 进入队列。当前排队: ${this.queue.length}`);
      }
    });
  }

  private lockAccount(account: Account, type: RequestType) {
    account.status = AccountStatus.BUSY;
    account.lastUsed = Date.now();
    account.totalUsage++;
    
    if (type === 'chat') account.usageChat++;
    if (type === 'image') account.usageImage++;
    if (type === 'video') account.usageVideo++;
    
    this.saveAccounts(); 
    logger.info(`[AccountManager] 账号 [${account.name}] 锁定 (Type: ${type})。`);
  }

  public releaseToken(token: string) {
    const account = this.accounts.find(a => a.token === token);
    if (!account) return;

    account.status = AccountStatus.COOLDOWN;
    logger.info(`[AccountManager] 账号 [${account.name}] 任务完成，进入 ${this.settings.cooldownTime/1000}s 冷却。`);

    setTimeout(() => {
      account.status = AccountStatus.IDLE;
      logger.info(`[AccountManager] 账号 [${account.name}] 冷却结束，恢复空闲。`);
      this.processQueue();
    }, this.settings.cooldownTime);
  }

  private processQueue() {
    if (this.queue.length === 0) return;

    // 遍历队列，寻找第一个能被满足的请求
    for (let i = 0; i < this.queue.length; i++) {
        const req = this.queue[i];
        const account = this.tryGetAvailableAccount(req.type);
        
        if (account) {
            this.queue.splice(i, 1);
            this.lockAccount(account, req.type);
            req.resolve(account);
            logger.info(`[AccountManager] 队列请求 [${req.type}] 已分配至 [${account.name}]。`);
            return; 
        }
    }
  }

  public getAccountsData() {
      // 计算剩余量辅助前端显示
      return this.accounts.map(a => ({
          ...a,
          remainingChat: a.limitChat === -1 ? '∞' : Math.max(0, a.limitChat - a.usageChat),
          remainingImage: Math.max(0, a.limitImage - a.usageImage),
          remainingVideo: Math.max(0, a.limitVideo - a.usageVideo),
          status: a.status
      }));
  }
  
  public getSettings() {
    return this.settings;
  }

  public getStats() {
      const usage = this.accounts.reduce((sums, a) => ({
          chat: sums.chat + (a.usageChat || 0),
          image: sums.image + (a.usageImage || 0),
          video: sums.video + (a.usageVideo || 0)
      }), { chat: 0, image: 0, video: 0 });

      return {
          totalAccounts: this.accounts.length,
          enabledAccounts: this.accounts.filter(a => a.enabled).length,
          statusCounts: {
              idle: this.accounts.filter(a => a.status === AccountStatus.IDLE && a.enabled).length,
              busy: this.accounts.filter(a => a.status === AccountStatus.BUSY).length,
              cooldown: this.accounts.filter(a => a.status === AccountStatus.COOLDOWN).length,
          },
          queue: this.queue.length,
          totalRemainingChat: this.getTotalRemainingUsage('chat'),
          totalRemainingImage: this.getTotalRemainingUsage('image'),
          totalRemainingVideo: this.getTotalRemainingUsage('video'),
          totalTokens: this.accounts.reduce((sum, a) => sum + (a.totalPromptTokens || 0) + (a.totalCompletionTokens || 0), 0),
          usage: usage
      };
  }

  public async addAccount(token: string, name: string, limits: any = {}, extra: any = {}) {
    const newAccount: Account = {
      id: util.uuid(),
      token,
      name: name || `账号 ${this.accounts.length + 1}`,
      enabled: true,
      type: extra.type || "doubao",
      weight: extra.weight || 1,
      baseUrl: extra.baseUrl || "",
      apiKey: extra.apiKey || "",
      capability: extra.capability || undefined,
      modelName: extra.modelName || "",
      deviceId: `7${util.generateRandomString({length: 18, charset: "numeric"})}`,
      webId: `7${util.generateRandomString({length: 18, charset: "numeric"})}`,
      userId: util.uuid(false),
      limitChat: limits.chat !== undefined ? limits.chat : -1,
      limitImage: limits.image !== undefined ? limits.image : 60,
      limitVideo: limits.video !== undefined ? limits.video : 0,
      usageChat: 0,
      usageImage: 0,
      usageVideo: 0,
      totalUsage: 0,
      totalPromptTokens: 0,
      totalCompletionTokens: 0,
      skipHealthCheck: !!extra.skipHealthCheck,
      status: AccountStatus.IDLE,
      lastUsed: 0,
      cooldownUntil: 0,
      cooldownReason: ""
    };

    this.accounts.push(newAccount);
    await this.saveAccounts();
    this.processQueue();
    return newAccount;
  }

  public async updateAccount(id: string, updates: Partial<Account>) {
    const index = this.accounts.findIndex((a) => a.id === id);
    if (index !== -1) {
      const wasEnabled = this.accounts[index].enabled;
      // 确保数值字段被正确转换
      if (updates.weight !== undefined) updates.weight = Number(updates.weight);
      if (updates.limitChat !== undefined) updates.limitChat = Number(updates.limitChat);
      if (updates.limitImage !== undefined) updates.limitImage = Number(updates.limitImage);
      if (updates.limitVideo !== undefined) updates.limitVideo = Number(updates.limitVideo);
      
      this.accounts[index] = { ...this.accounts[index], ...updates };
      if (!wasEnabled && updates.enabled) this.processQueue();
      await this.saveAccounts();
      return this.accounts[index];
    }
    return null;
  }

  /**
   * 应用响应码策略
   * @param id 账号ID
   * @param statusCode HTTP 状态码
   * @returns 处理动作 (retry | cooldown | etc)
   */
  public applyResponsePolicy(id: string, statusCode: number): PolicyAction | null {
    const account = this.accounts.find(a => a.id === id);
    if (!account) return null;

    const policy = ResponsePolicyManager.getPolicyForStatus(statusCode, account.type);
    if (!policy) return null;

    logger.warn(`[AccountManager] 触发响应策略: 账号 [${account.name}] 遇到 [${statusCode}], 动作: ${policy.action} (${policy.description})`);

    switch (policy.action) {
      case "disable":
        account.enabled = false;
        break;
      case "cooldown_1h":
        account.cooldownUntil = Date.now() + 3600 * 1000;
        account.cooldownReason = `Status ${statusCode}: ${policy.description}`;
        break;
      case "cooldown_24h":
        account.cooldownUntil = Date.now() + 24 * 3600 * 1000;
        account.cooldownReason = `Status ${statusCode}: ${policy.description}`;
        break;
    }

    this.saveAccounts();
    return policy.action;
  }



  /**
   * 更新账号用量和 Token 统计
   */
  public async updateAccountUsage(id: string, type: AccountCapability, promptTokens: number = 0, completionTokens: number = 0) {
    const account = this.accounts.find(a => a.id === id);
    if (!account) return;

    if (type === 'chat') {
      account.usageChat += 1;
    } else if (type === 'image') {
      account.usageImage += 1;
    } else if (type === 'video') {
      account.usageVideo += 1;
    }
    
    account.totalUsage += 1;
    account.totalPromptTokens += promptTokens;
    account.totalCompletionTokens += completionTokens;

    await this.saveAccounts();
  }

  /**
   * 获取所有可用的模型列表
   */
  public getAvailableModels() {
    const models = [
      { id: "doubao", object: "model", owned_by: "doubao-free-api" },
      { id: "doubao-video", object: "model", owned_by: "doubao-free-api" },
      { id: "doubao-image", object: "model", owned_by: "doubao-free-api" }
    ];
    return models;
  }

  /**
   * 检查所有账号健康状态
   */
  public async checkAllAccountsHealth() {
    logger.info(`[AccountManager] 开始执行账号健康检查...`);
    for (const account of this.accounts) {
       if (!account.enabled || account.skipHealthCheck) continue;
       const isHealthy = await this.checkAccountHealth(account);
       account.lastHealthCheck = Date.now();
       account.healthStatus = isHealthy ? "healthy" : "unhealthy";
       if (!isHealthy) {
          logger.error(`[AccountManager] 账号健康检查失败: [${account.name}] (${account.type})`);
          // 如果是豆包账号 session 失效，可以考虑自动禁用或仅标记
          // account.enabled = false; 
       }
    }
    await this.saveAccounts();
  }

  /**
   * 检查单个账号健康状态
   */
  public async checkAccountHealth(account: Account): Promise<boolean> {
    try {
      if (account.type === 'doubao') {
        const res = await axios.get("https://www.doubao.com/im/conversation/info", {
          headers: {
            "Cookie": `sessionid=${account.token}`,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
          },
          timeout: 10000,
          validateStatus: () => true 
        });
        // 豆包接口非 200 或 code 异常通常意味着 session 过期
        const healthy = res.status === 200 && (!res.data || res.data.code !== 401);
        if (!healthy) account.healthError = `HTTP ${res.status}: ${JSON.stringify(res.data)}`;
        else account.healthError = undefined;
        return healthy;
      } else {
        const url = (account.baseUrl || "").replace(/\/$/, "") + "/v1/models";
        const res = await axios.get(url, {
          headers: { "Authorization": `Bearer ${account.apiKey}` },
          timeout: 10000,
          validateStatus: () => true
        });
        const healthy = res.status === 200;
        if (!healthy) account.healthError = `HTTP ${res.status}`;
        else account.healthError = undefined;
        return healthy;
      }
    } catch (e: any) {
      account.healthError = e.message;
      return false;
    }
  }

  public async deleteAccount(id: string) {

    this.accounts = this.accounts.filter((a) => a.id !== id);
    await this.saveAccounts();
  }

  public async resetDailyUsage() {
    this.accounts.forEach(acc => {
        acc.usageChat = 0;
        acc.usageImage = 0;
        acc.usageVideo = 0;
    });
    await this.saveAccounts();
    this.processQueue();
  }
}

export default new AccountManager();
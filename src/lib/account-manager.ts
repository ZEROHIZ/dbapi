import fs from "fs-extra";
import path from "path";
import util from "@/lib/util.ts";
import logger from "@/lib/logger.ts";
import cron from "cron";
import { EventEmitter } from "events";

const DATA_DIR = path.join(process.cwd(), "data");
const ACCOUNTS_FILE = path.join(DATA_DIR, "accounts.json");
const SETTINGS_FILE = path.join(DATA_DIR, "settings.json");

export enum AccountStatus {
  IDLE = "idle",
  BUSY = "busy",
  COOLDOWN = "cooldown"
}

export interface Account {
  id: string;
  token: string;
  name: string;
  enabled: boolean;
  
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
  
  // 运行时状态
  status?: AccountStatus;
  lastUsed?: number;
  
  // 兼容旧字段（读取时转换，保存时废弃）
  dailyLimit?: number;
  dailyUsage?: number;
}

export interface Settings {
  cooldownTime: number; // 毫秒
}

export type RequestType = "chat" | "image" | "video";

class AccountManager extends EventEmitter {
  private accounts: Account[] = [];
  private settings: Settings = {
    cooldownTime: 10000,
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
        deviceId: a.deviceId, webId: a.webId, userId: a.userId,
        limitChat: a.limitChat, limitImage: a.limitImage, limitVideo: a.limitVideo,
        usageChat: a.usageChat, usageImage: a.usageImage, usageVideo: a.usageVideo,
        totalUsage: a.totalUsage
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
    return this.accounts.find(a => {
        if (!a.enabled || a.status !== AccountStatus.IDLE) return false;
        
        // 检查对应额度
        if (type === 'chat' && a.limitChat !== -1 && a.usageChat >= a.limitChat) return false;
        if (type === 'image' && a.usageImage >= a.limitImage) return false;
        if (type === 'video' && a.usageVideo >= a.limitVideo) return false;
        
        return true;
    }) || null;
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
      };
  }

  public async addAccount(token: string, name: string, limits: { chat?: number, image?: number, video?: number } = {}) {
    const newAccount: Account = {
      id: util.uuid(),
      token,
      name: name || `账号 ${this.accounts.length + 1}`,
      enabled: true,
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
      status: AccountStatus.IDLE,
      lastUsed: 0
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
      this.accounts[index] = { ...this.accounts[index], ...updates };
      if (!wasEnabled && updates.enabled) this.processQueue();
      await this.saveAccounts();
      return this.accounts[index];
    }
    return null;
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
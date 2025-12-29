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
  dailyUsage: number;
  totalUsage: number;
  dailyLimit: number;
  // 运行时状态
  status?: AccountStatus;
  lastUsed?: number;
}

export interface Settings {
  cooldownTime: number; // 毫秒
}

class AccountManager extends EventEmitter {
  private accounts: Account[] = [];
  private settings: Settings = {
    cooldownTime: 10000, // 默认10秒
  };
  
  // 存储等待中的 Promise 及其 reject/resolve
  private queue: Array<{ resolve: (token: string) => void, reject: (err: any) => void }> = [];

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
            dailyLimit: s.dailyLimit || 100
        }));
      }
    } catch (e) {
      logger.error("加载账号文件失败:", e);
    }
  }

  private async saveAccounts() {
    try {
      const toSave = this.accounts.map(({ id, token, name, enabled, dailyUsage, totalUsage, dailyLimit }) => ({
        id, token, name, enabled, dailyUsage, totalUsage, dailyLimit
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

  /**
   * 计算当前所有可用账号的总剩余次数
   */
  public getTotalRemainingUsage(): number {
      return this.accounts
          .filter(a => a.enabled)
          .reduce((sum, a) => sum + Math.max(0, a.dailyLimit - a.dailyUsage), 0);
  }

  private tryGetAvailableAccount(): Account | null {
    return this.accounts.find(a => 
      a.enabled && 
      a.status === AccountStatus.IDLE && 
      a.dailyUsage < a.dailyLimit
    ) || null;
  }

  /**
   * 外部获取 Token 的核心入口
   */
  public acquireToken(): Promise<string> {
    return new Promise((resolve, reject) => {
      const remaining = this.getTotalRemainingUsage();
      
      // 检查排队限制：排队人数不能超过总剩余次数
      if (this.queue.length >= remaining && remaining > 0) {
          return reject(new Error(`系统繁忙：排队人数(${this.queue.length})已达到今日剩余额度上限(${remaining})。`));
      }
      
      if (remaining <= 0) {
          return reject(new Error("系统今日额度已耗尽。"));
      }

      const account = this.tryGetAvailableAccount();
      if (account) {
        this.lockAccount(account);
        resolve(account.token);
      } else {
        // 进入队列等待空闲或冷却结束
        this.queue.push({ resolve, reject });
        logger.info(`[AccountManager] 暂无空闲账号，进入队列。当前排队: ${this.queue.length}`);
      }
    });
  }

  private lockAccount(account: Account) {
    account.status = AccountStatus.BUSY;
    account.lastUsed = Date.now();
    account.dailyUsage++;
    account.totalUsage++;
    this.saveAccounts(); 
    logger.info(`[AccountManager] 账号 [${account.name}] 已锁定并开始任务。今日已用: ${account.dailyUsage}/${account.dailyLimit}`);
  }

  /**
   * 任务结束后的释放入口
   */
  public releaseToken(token: string) {
    const account = this.accounts.find(a => a.token === token);
    if (!account) return;

    // 状态切换到冷却中
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

    const account = this.tryGetAvailableAccount();
    if (account) {
      const nextRequest = this.queue.shift();
      if (nextRequest) {
        this.lockAccount(account);
        nextRequest.resolve(account.token);
        logger.info(`[AccountManager] 队列请求已分配至 [${account.name}]。剩余排队: ${this.queue.length}`);
      }
    }
  }

  // --- API 数据获取 ---

  public getAccountsData() {
    return this.accounts.map(a => ({
        ...a,
        remaining: Math.max(0, a.dailyLimit - a.dailyUsage),
        status: a.status
    }));
  }

  public getSettings() {
    return this.settings;
  }
  
  public getStats() {
      const remaining = this.getTotalRemainingUsage();
      return {
          totalAccounts: this.accounts.length,
          enabledAccounts: this.accounts.filter(a => a.enabled).length,
          statusCounts: {
              idle: this.accounts.filter(a => a.status === AccountStatus.IDLE && a.enabled).length,
              busy: this.accounts.filter(a => a.status === AccountStatus.BUSY).length,
              cooldown: this.accounts.filter(a => a.status === AccountStatus.COOLDOWN).length,
          },
          queue: {
              current: this.queue.length,
              limit: remaining
          },
          totalRemaining: remaining
      };
  }

  public async addAccount(token: string, name: string, limit: number = 100) {
    const newAccount: Account = {
      id: util.uuid(),
      token,
      name: name || `账号 ${this.accounts.length + 1}`,
      enabled: true,
      dailyUsage: 0,
      totalUsage: 0,
      dailyLimit: limit,
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
    this.accounts.forEach(acc => acc.dailyUsage = 0);
    await this.saveAccounts();
    this.processQueue();
  }
}

export default new AccountManager();

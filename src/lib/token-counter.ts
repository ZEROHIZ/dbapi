import fs from "fs-extra";
import path from "path";
import logger from "@/lib/logger.ts";

const DATA_DIR = path.join(process.cwd(), "data");
const USAGE_STATS_FILE = path.join(DATA_DIR, "usage-stats.json");

export interface UsageMetric {
  promptTokens: number;
  completionTokens: number;
  count: number;
}

export interface UsageStats {
  total: UsageMetric;
  byAccount: Record<string, UsageMetric>;
}

class TokenCounter {
  private stats: UsageStats = {
    total: { promptTokens: 0, completionTokens: 0, count: 0 },
    byAccount: {}
  };

  constructor() {
    this.init();
  }

  private async init() {
    await fs.ensureDir(DATA_DIR);
    await this.loadStats();
  }

  private async loadStats() {
    try {
      if (await fs.pathExists(USAGE_STATS_FILE)) {
        this.stats = await fs.readJson(USAGE_STATS_FILE);
      }
    } catch (e) {
      logger.error("加载用量统计失败:", e);
    }
  }

  private async saveStats() {
    try {
      await fs.writeJson(USAGE_STATS_FILE, this.stats, { spaces: 2 });
    } catch (e) {
      logger.error("保存用量统计失败:", e);
    }
  }

  /**
   * 估算 Token 数量
   * 这是一个比较粗略的估算：
   * 中文：每个字符约 0.6 token (或者按 1个汉字=1.5~2tokens)
   * 英文：每个单词约 1.3 token，或者每 4 个字符 1 token
   * 这里采用保守估算：中文 2 tokens/字符，英文 0.5 token/字符
   */
  public estimateTokens(text: string): number {
    if (!text) return 0;
    let tokens = 0;
    for (let i = 0; i < text.length; i++) {
      const charCode = text.charCodeAt(i);
      if (charCode > 255) {
        tokens += 2; // 中文等双字节字符
      } else {
        tokens += 0.5; // 英文等单字节字符
      }
    }
    return Math.ceil(tokens);
  }

  /**
   * 记录用量
   */
  public async recordUsage(accountId: string, promptTokens: number, completionTokens: number) {
    // 更新全局统计
    this.stats.total.promptTokens += promptTokens;
    this.stats.total.completionTokens += completionTokens;
    this.stats.total.count += 1;

    // 更新各账号统计
    if (!this.stats.byAccount[accountId]) {
      this.stats.byAccount[accountId] = { promptTokens: 0, completionTokens: 0, count: 0 };
    }
    this.stats.byAccount[accountId].promptTokens += promptTokens;
    this.stats.byAccount[accountId].completionTokens += completionTokens;
    this.stats.byAccount[accountId].count += 1;

    await this.saveStats();
  }

  public getStats(): UsageStats {
    return this.stats;
  }
}

export default new TokenCounter();

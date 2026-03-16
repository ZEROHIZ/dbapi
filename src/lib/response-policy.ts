import fs from "fs-extra";
import path from "path";
import logger from "@/lib/logger.ts";

const DATA_DIR = path.join(process.cwd(), "data");
const POLICY_FILE = path.join(DATA_DIR, "response-policies.json");

export type PolicyAction = "retry" | "cooldown_1h" | "cooldown_24h" | "disable";

export interface ResponsePolicy {
  statusCode: number;      // HTTP 状态码
  action: PolicyAction;    // 处理动作
  description: string;     // 描述
  applyTo: "all" | "doubao" | "openai";  // 适用范围
}

const DEFAULT_POLICIES: ResponsePolicy[] = [
  { statusCode: 401, action: "cooldown_24h", description: "认证失败，停用24小时", applyTo: "all" },
  { statusCode: 403, action: "cooldown_24h", description: "权限被拒，停用24小时", applyTo: "all" },
  { statusCode: 429, action: "cooldown_1h",  description: "请求频率限制，冷却1小时", applyTo: "all" },
  { statusCode: 500, action: "retry",        description: "服务器错误，换号重试", applyTo: "all" },
  { statusCode: 502, action: "retry",        description: "网关错误，换号重试", applyTo: "all" },
  { statusCode: 503, action: "retry",        description: "服务不可用，换号重试", applyTo: "all" },
  { statusCode: -2001, action: "retry",      description: "API请求失败，换号重试", applyTo: "doubao" },
];

class ResponsePolicyManager {
  private policies: ResponsePolicy[] = [];

  constructor() {
    this.init();
  }

  private async init() {
    await fs.ensureDir(DATA_DIR);
    await this.loadPolicies();
  }

  public async loadPolicies() {
    try {
      if (await fs.pathExists(POLICY_FILE)) {
        this.policies = await fs.readJson(POLICY_FILE);
      } else {
        this.policies = [...DEFAULT_POLICIES];
        await this.savePolicies(this.policies);
      }
    } catch (e) {
      logger.error("加载策略文件失败:", e);
      this.policies = [...DEFAULT_POLICIES];
    }
  }

  public async savePolicies(policies: ResponsePolicy[]) {
    this.policies = policies;
    try {
      await fs.writeJson(POLICY_FILE, this.policies, { spaces: 2 });
    } catch (e) {
      logger.error("保存策略文件失败:", e);
    }
  }

  public getPolicies(): ResponsePolicy[] {
    return this.policies;
  }

  public getPolicyForStatus(statusCode: number, type: "doubao" | "openai"): ResponsePolicy | null {
    const policy = this.policies.find(p => p.statusCode === statusCode && (p.applyTo === "all" || p.applyTo === type));
    if (policy) return policy;

    // 默认回退逻辑：对于未定义的 5xx 错误或 负数业务错误码，默认尝试换号重试一次
    if (statusCode >= 500 || statusCode < 0) {
      return {
        statusCode,
        action: "retry",
        description: `未定义错误 ${statusCode}，启用默认重试策略`,
        applyTo: "all"
      };
    }

    return null;
  }
}

export default new ResponsePolicyManager();

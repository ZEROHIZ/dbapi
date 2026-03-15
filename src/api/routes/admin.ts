import AccountManager from "@/lib/account-manager.ts";
import SuccessfulBody from "@/lib/response/SuccessfulBody.ts";
import fs from "fs-extra";
import Response from "@/lib/response/Response.ts";
import path from "path";
import environment from "@/lib/environment.ts";

// 读取版本号
const getVersion = async () => {
    try {
        const packageJsonPath = path.join(process.cwd(), 'package.json');
        const packageJson = await fs.readJson(packageJsonPath);
        return packageJson.version || 'unknown';
    } catch {
        return 'unknown';
    }
};

/**
 * 验证管理权限
 * @param req 请求对象
 */
const checkAuth = (req: any) => {
    const password = environment.adminPassword;
    if (!password) return true; // 未设置密码则不验证

    const auth = req.headers['authorization'] || '';
    const token = auth.replace('Bearer ', '');
    return token === password;
};

/**
 * 认证包装器
 */
const withAuth = (fn: Function) => {
    return async (req: any) => {
        if (!checkAuth(req)) {
            return new Response({ code: 401, msg: "Unauthorized: Invalid or missing admin password" }, { statusCode: 401 });
        }
        return await fn(req);
    };
};

export default {
    get: {
        '/admin': async () => {
            // ... (同前，不保护页面本身以便加载登录逻辑)
            let filePath = 'public/admin.html';
            if (!await fs.pathExists(filePath)) filePath = path.join(process.cwd(), 'admin.html');
            if (!await fs.pathExists(filePath)) filePath = path.join(process.cwd(), 'public', 'admin.html');

            if (await fs.pathExists(filePath)) {
                const content = await fs.readFile(filePath);
                return new Response(content, { type: 'html', headers: { 'Content-Type': 'text/html; charset=utf-8', Expires: '-1' } });
            }
            return new Response("Admin page not found.", { statusCode: 404 });
        },
        '/admin/accounts': withAuth(async () => {
            const accounts = AccountManager.getAccountsData();
            return new SuccessfulBody(accounts);
        }),
        '/admin/stats': withAuth(async () => {
            const stats = AccountManager.getStats();
            return new SuccessfulBody(stats);
        }),
        '/admin/settings': withAuth(async () => {
            const settings = AccountManager.getSettings();
            return new SuccessfulBody(settings);
        }),
        '/admin/version': async () => { // 版本号允许公开查看
            const version = await getVersion();
            return new SuccessfulBody({ version });
        }
    },
    post: {
        '/admin/login': async (req: any) => {
            const { password } = req.body;
            if (environment.adminPassword && password !== environment.adminPassword) {
                return new Response({ code: 401, msg: "Invalid password" }, { statusCode: 401 });
            }
            return new SuccessfulBody({ message: "Login successful", token: environment.adminPassword || "" });
        },
        '/admin/accounts': withAuth(async (req: any) => {
            try {
                const body = req.body;
                if (!body) throw new Error("Request body is required");
                const { token, name, limitChat, limitImage, limitVideo, ...extra } = body;
                const limits = { 
                    chat: parseInt(limitChat) || -1, 
                    image: parseInt(limitImage) || 60, 
                    video: parseInt(limitVideo) || 0 
                };
                // 将 token 传入 addAccount，如果 type 为 openai，token 可能是空，由 extra 中的 apiKey 补充
                const newAccount = await AccountManager.addAccount(token || "", name, limits, extra);
                return new SuccessfulBody(newAccount);
            } catch (err: any) {
                return new Response({ code: 400, msg: err.message }, { statusCode: 400 });
            }
        }),
        '/admin/accounts/:id': withAuth(async (req: any) => {
            const { id } = req.params;
            const updates = req.body;
            const updated = await AccountManager.updateAccount(id, updates);
            return new SuccessfulBody(updated);
        }),
        '/admin/settings': withAuth(async (req: any) => {
            const settings = req.body;
            await AccountManager.saveSettings(settings);
            return new SuccessfulBody({ message: "Settings saved" });
        }),
        '/admin/reset-all': withAuth(async () => {
            await AccountManager.resetDailyUsage();
            return new SuccessfulBody({ message: "All daily usage reset" });
        })
    },
    delete: {
        '/admin/accounts/:id': withAuth(async (req: any) => {
            const { id } = req.params;
            await AccountManager.deleteAccount(id);
            return new SuccessfulBody({ message: "Account deleted" });
        })
    }
};

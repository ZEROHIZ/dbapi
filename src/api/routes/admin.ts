import AccountManager from "@/lib/account-manager.ts";
import SuccessfulBody from "@/lib/response/SuccessfulBody.ts";
import fs from "fs-extra";
import Response from "@/lib/response/Response.ts";
import path from "path";

export default {
    get: {
        '/admin': async () => {
             // 兼容开发环境和生产环境（dist）
             let filePath = 'public/admin.html';
             if (!await fs.pathExists(filePath)) {
                 filePath = path.join(process.cwd(), 'admin.html');
             }
             if (!await fs.pathExists(filePath)) {
                 filePath = path.join(process.cwd(), 'public', 'admin.html');
             }

             if (await fs.pathExists(filePath)) {
                const content = await fs.readFile(filePath);
                return new Response(content, {
                    type: 'html',
                    headers: {
                        'Content-Type': 'text/html; charset=utf-8',
                         Expires: '-1'
                    }
                });
             } else {
                 return new Response("Admin page not found. Please ensure public/admin.html exists.", { status: 404 });
             }
        },
        '/admin/accounts': async () => {
            const accounts = AccountManager.getAccountsData();
            return new SuccessfulBody(accounts);
        },
        '/admin/stats': async () => {
            const stats = AccountManager.getStats();
            return new SuccessfulBody(stats);
        },
        '/admin/settings': async () => {
            const settings = AccountManager.getSettings();
            return new SuccessfulBody(settings);
        }
    },
    post: {
        '/admin/accounts': async (req: any) => {
            try {
                // Request 对象直接包含 body
                const body = req.body;
                if (!body || !body.token) {
                    throw new Error("Token is required");
                }
                const { token, name, dailyLimit } = body;
                const newAccount = await AccountManager.addAccount(token, name, parseInt(dailyLimit) || 100);
                return new SuccessfulBody(newAccount);
            } catch (err: any) {
                return new Response({ code: 400, msg: err.message }, { statusCode: 400 });
            }
        },
        '/admin/accounts/:id': async (req: any) => {
            const { id } = req.params;
            const updates = req.body;
            const updated = await AccountManager.updateAccount(id, updates);
            return new SuccessfulBody(updated);
        },
        '/admin/settings': async (req: any) => {
            const settings = req.body;
            await AccountManager.saveSettings(settings);
            return new SuccessfulBody({ message: "Settings saved" });
        },
        '/admin/reset-all': async () => {
            await AccountManager.resetDailyUsage();
            return new SuccessfulBody({ message: "All daily usage reset" });
        }
    },
    delete: {
        '/admin/accounts/:id': async (req: any) => {
            const { id } = req.params;
            await AccountManager.deleteAccount(id);
            return new SuccessfulBody({ message: "Account deleted" });
        }
    }
};

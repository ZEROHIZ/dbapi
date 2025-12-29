import fs from 'fs-extra';
import path from 'path';

const DEBUG_DIR = path.join(process.cwd(), 'logs', 'debug_dumps');

/**
 * 追加文本到同一个文件
 * @param filenameBase 文件名（不含路径）
 * @param text 要追加的文本
 */
export async function appendDumpText(filenameBase: string, text: string) {
    try {
        await fs.ensureDir(DEBUG_DIR);
        const filePath = path.join(DEBUG_DIR, filenameBase);
        // 直接追加原始内容，不做额外处理，保证原汁原味
        await fs.appendFile(filePath, text);
    } catch (err) {
        console.error(`[DebugDumper] 追加失败 [${filenameBase}]:`, err);
    }
}

/**
 * 保存对象（用于轮询数据）
 */
export async function dumpObject(name: string, data: any) {
    try {
        await fs.ensureDir(DEBUG_DIR);
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `${timestamp}_${name}.json`;
        const filePath = path.join(DEBUG_DIR, filename);
        await fs.writeFile(filePath, JSON.stringify(data, null, 2));
    } catch (err) {
        console.error(`[DebugDumper] 保存失败 [${name}]:`, err);
    }
}

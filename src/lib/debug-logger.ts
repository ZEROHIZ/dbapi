import fs from 'fs';
import path from 'path';
import util from '@/lib/util.ts';

const LOG_FILE_PATH = path.join(process.cwd(), 'request_debug.jsonl');

export function logRequest(method: string, url: string, params: any, headers: any, data: any) {
    const logEntry = {
        timestamp: new Date().toISOString(),
        method,
        url,
        params,
        headers,
        data,
    };

    const logString = JSON.stringify(logEntry) + '\n';

    fs.appendFile(LOG_FILE_PATH, logString, (err) => {
        if (err) {
            console.error('Failed to write to debug log:', err);
        }
    });
}

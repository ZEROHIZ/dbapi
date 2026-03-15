import _ from 'lodash';
import AccountManager from '@/lib/account-manager.ts';

export default {

    prefix: '/v1',

    get: {
        '/models': async () => {
            const models = AccountManager.getAvailableModels();
            return {
                "data": models
            };
        }

    }
}
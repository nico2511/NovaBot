const os = require('os');
const fs = require('fs');

const isWin = os.platform() === 'win32';

// Auto-detect venv folder (.venv or venv)
let venvDir = './venv';
if (fs.existsSync('./.venv')) {
    venvDir = './.venv';
}

// Logic to determine python interpreter path based on OS
const interpreterPath = isWin
    ? `${venvDir}/Scripts/python.exe`
    : `${venvDir}/bin/python`;

module.exports = {
    apps: [
        {
            name: 'novabot-backend',
            script: 'backend/api.py',
            interpreter: interpreterPath,
            interpreter_args: '-X utf8',
            cwd: process.cwd(),
            env: {
                PYTHONPATH: process.cwd(),
                VIRTUAL_ENV: process.cwd() + (venvDir.startsWith('./') ? venvDir.substring(1) : '/' + venvDir),
                PYTHONIOENCODING: 'utf-8',
                PORT: 8001
            },
            error_file: './logs/backend-error.log',
            out_file: './logs/backend-out.log',
            log_date_format: 'YYYY-MM-DD HH:mm:ss',
            autorestart: true,
            max_restarts: 10,
            min_uptime: '5s'
        },
        {
            name: 'novabot-frontend',
            script: 'npm',
            args: 'start',
            cwd: './frontend-v3',
            env: {
                NODE_ENV: 'production',
                PORT: 3000
            },
            error_file: '../logs/frontend-error.log',
            out_file: '../logs/frontend-out.log',
            log_date_format: 'YYYY-MM-DD HH:mm:ss',
            autorestart: true,
            max_restarts: 10,
            min_uptime: '5s'
        }
    ]
}

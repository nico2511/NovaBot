module.exports = {
  apps: [
    {
      name: 'hl-bot-engine',
      script: 'main_nextjs.py',
      interpreter: './.venv/bin/python',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: process.cwd(),
        VIRTUAL_ENV: process.cwd() + '/.venv'
      },
      error_file: './logs/bot-error.log',
      out_file: './logs/bot-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s'
    },
    {
      name: 'hl-api',
      script: './.venv/bin/uvicorn',
      args: 'backend.api:app --host 0.0.0.0 --port 8001',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: process.cwd(),
        VIRTUAL_ENV: process.cwd() + '/.venv'
      },
      error_file: './logs/api-error.log',
      out_file: './logs/api-out.log',
      autorestart: true
    },
    {
      name: 'hl-frontend',
      script: 'node_modules/next/dist/bin/next',
      args: 'start -p 3000',
      cwd: './frontend',
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log',
      autorestart: true
    }
  ]
}

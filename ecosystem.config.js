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
      name: 'hl-frontend',
      script: 'npm',
      args: 'start',
      cwd: './frontend',
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log',
      autorestart: true
    }
  ]
}

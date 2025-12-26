module.exports = {
    apps: [
        {
            name: "hl-bot-engine",
            script: "main_nextjs.py",
            interpreter: "./.venv/bin/python3",
            autorestart: true,
            watch: false,
            env: {
                PYTHONUNBUFFERED: "1"
            }
        },
        {
            name: "hl-frontend",
            script: "npm",
            args: "start",
            cwd: "./frontend",
            autorestart: true,
            watch: false,
            env: {
                PORT: 3000,
                NODE_ENV: "production"
            }
        }
    ]
}

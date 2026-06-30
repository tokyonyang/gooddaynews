# Root Vercel deployment should use JS API only.
# Python webhook is isolated under vercel-webhook/ and should be used with Root Directory=vercel-webhook.
*.py
pyproject.toml
__pycache__/
**/__pycache__/
*.pyc
api/telegram_webhook/
vercel-webhook/
reports/
.env
*.zip

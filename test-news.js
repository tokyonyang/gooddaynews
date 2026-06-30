name: telegram-webhook-control

"on":
  workflow_dispatch:
    inputs:
      action:
        description: "Webhook action"
        required: true
        default: "set"
        type: choice
        options:
          - set
          - info
          - delete
      webhook_url:
        description: "Vercel project URL or full webhook URL. Empty = vars.TELEGRAM_WEBHOOK_URL"
        required: false
        default: ""
      drop_pending_updates:
        description: "Drop old Telegram updates when setting/deleting webhook"
        required: false
        default: "true"
        type: choice
        options:
          - "true"
          - "false"

permissions:
  contents: read

jobs:
  telegram-webhook-control:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install requests python-dotenv

      - name: Control Telegram webhook
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_WEBHOOK_SECRET: ${{ secrets.TELEGRAM_WEBHOOK_SECRET }}
          TELEGRAM_WEBHOOK_URL: ${{ github.event.inputs.webhook_url || vars.TELEGRAM_WEBHOOK_URL }}
          TELEGRAM_WEBHOOK_ACTION: ${{ github.event.inputs.action }}
          TELEGRAM_WEBHOOK_DROP_PENDING: ${{ github.event.inputs.drop_pending_updates }}
        run: >
          python scripts/telegram_webhook_control.py
          --action "$TELEGRAM_WEBHOOK_ACTION"
          --url "$TELEGRAM_WEBHOOK_URL"
          --drop-pending-updates "$TELEGRAM_WEBHOOK_DROP_PENDING"

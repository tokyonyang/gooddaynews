name: morning-briefing

"on":
  workflow_dispatch:
  schedule:
    # 매일 05:57 KST = 전일 20:57 UTC
    - cron: "57 20 * * *"

permissions:
  contents: read

jobs:
  morning-briefing:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Send morning briefing
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GEMINI_MODEL: ${{ vars.GEMINI_MODEL || 'gemini-2.5-flash' }}
          NAVER_CLIENT_ID: ${{ secrets.NAVER_CLIENT_ID }}
          NAVER_CLIENT_SECRET: ${{ secrets.NAVER_CLIENT_SECRET }}
          NEWS_PROVIDER: ${{ vars.NEWS_PROVIDER || 'naver_first' }}

          DEFAULT_REGION: ${{ vars.DEFAULT_REGION || 'KR' }}
          DEFAULT_LOCALE: ${{ vars.DEFAULT_LOCALE || 'ko-KR' }}
          DEFAULT_TIMEZONE: ${{ vars.DEFAULT_TIMEZONE || 'Asia/Seoul' }}
          SUPPORTING_NEWS_MAX_AGE_HOURS: ${{ vars.SUPPORTING_NEWS_MAX_AGE_HOURS || '48' }}
          EXCLUDE_UNKNOWN_PUBLISHED_AT: ${{ vars.EXCLUDE_UNKNOWN_PUBLISHED_AT || 'true' }}

          WEATHER_ENABLED: ${{ vars.WEATHER_ENABLED || 'true' }}
          WEATHER_DEFAULT_CITY: ${{ vars.WEATHER_DEFAULT_CITY || '서울' }}
          WEATHER_DEFAULT_LAT: ${{ vars.WEATHER_DEFAULT_LAT || '37.5665' }}
          WEATHER_DEFAULT_LON: ${{ vars.WEATHER_DEFAULT_LON || '126.9780' }}

          TELEGRAM_URL_BUTTONS: ${{ vars.TELEGRAM_URL_BUTTONS || 'true' }}
          TELEGRAM_LINK_BUTTON_LIMIT: ${{ vars.TELEGRAM_LINK_BUTTON_LIMIT || '8' }}

          MORNING_TOPIC_LIMIT: ${{ vars.MORNING_TOPIC_LIMIT || '10' }}
          MORNING_LINKS_PER_TOPIC: ${{ vars.MORNING_LINKS_PER_TOPIC || '2' }}
          MORNING_LINK_BUTTON_LIMIT: ${{ vars.MORNING_LINK_BUTTON_LIMIT || '8' }}
          MORNING_LOOKBACK_HOURS: ${{ vars.MORNING_LOOKBACK_HOURS || '24' }}
          MORNING_INCLUDE_GLOBAL_BREAKING: ${{ vars.MORNING_INCLUDE_GLOBAL_BREAKING || 'true' }}
          MORNING_GLOBAL_BREAKING_COUNT: ${{ vars.MORNING_GLOBAL_BREAKING_COUNT || '3' }}
          MORNING_BRIEFING_TOPICS: ${{ vars.MORNING_BRIEFING_TOPICS || '' }}
          GLOBAL_BREAKING_NEWS_USE_DIRECT_SITES: ${{ vars.GLOBAL_BREAKING_NEWS_USE_DIRECT_SITES || 'true' }}
          GLOBAL_BREAKING_SOCIAL_FEEDS: ${{ vars.GLOBAL_BREAKING_SOCIAL_FEEDS || '' }}
        run: python morning_briefing.py

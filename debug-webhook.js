{
  "crons": [
    {
      "path": "/api/morning-briefing",
      "schedule": "30 22 * * *"
    }
  ],
  "functions": {
    "api/*.js": {
      "maxDuration": 60
    }
  }
}

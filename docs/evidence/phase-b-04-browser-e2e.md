# Phase B-04 — Browser E2E

Date: 2026-10-01

## Route under test

`Chrome -> Next.js production build -> FastAPI JWT -> PostgreSQL -> Redis/Dramatiq worker -> PostgreSQL -> FastAPI polling -> Next.js result`

## Inputs and assertions

- Craft: 中国剪纸
- Platform: B站
- Duration: 90秒
- Aspect ratio: 16:9
- Tone: 纪录片
- JWT identity: persistent staging workspace owner

The browser asserted the returned script displayed the same platform, duration, aspect ratio and tone,
showed independent verification and exposed knowledge evidence. The worker produced the terminal run and
the page polled it to completion.

The final acceptance run targeted the fully containerized staging frontend at
`http://127.0.0.1:13000`, rather than host-started development processes.

## Result

```json
{
  "status": "passed",
  "checks": {
    "platform": true,
    "spec": true,
    "tone": true,
    "verification": true,
    "evidence": true
  },
  "browser_exceptions": []
}
```

Artifacts:

- `artifacts/e2e/phase-b-next-pipeline.json`
- `artifacts/e2e/phase-b-next-pipeline.png`

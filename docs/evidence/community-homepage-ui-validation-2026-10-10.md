# Community homepage UI validation — 2026-10-10

## Build evidence

```text
pnpm lint
exit code: 0

pnpm build
Compiled successfully
Finished TypeScript in 1301ms
Generated static pages (6/6)
exit code: 0
```

## Runtime evidence

```text
http://127.0.0.1:3000/                    200
http://127.0.0.1:3000/?channel=embroidery 200
http://127.0.0.1:3000/creator             200
```

## Visual evidence

- `.test-artifacts/community-v2-20261010/home-1440.png`
- `.test-artifacts/community-v2-20261010/home-1024.png`
- `.test-artifacts/community-v2-20261010/home-768.png`

The screenshots were captured from the running local site with Edge headless mode.

## Acceptance checklist

- [x] HAHA brand presentation state
- [x] Banner leaves the viewport naturally
- [x] 96/32px hysteresis compact-header state machine
- [x] Header and Channel Bar share one sticky system
- [x] Compact and grouped expanded channels
- [x] Active channel stored in URL
- [x] Shared 1440px content boundary
- [x] Unified content cards and feed density
- [x] Content type and region dimensions separated
- [x] Regional discovery and culture-map entry
- [x] Topic curation
- [x] Creator tools, AI script and conversation-workspace entries
- [x] Keyboard focus, Escape and ARIA state
- [x] Passive + requestAnimationFrame scroll processing
- [x] 1440, 1024 and 768 visual validation
- [x] No nested page scrollbar or horizontal overflow observed
- [x] HAHA color, typography and editorial identity retained

No Production Candidate status is asserted.

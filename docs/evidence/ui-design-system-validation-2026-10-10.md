# UI Design System validation evidence — 2026-10-10

## Static verification

```text
pnpm lint
exit code: 0

pnpm build
Compiled successfully
Finished TypeScript in 6.0s
Generated static pages (6/6)
exit code: 0
```

The sandboxed build compiled and then hit the known child-process `spawn EPERM`; the permitted build
completed TypeScript and static generation successfully.

## Runtime routes

```text
http://127.0.0.1:3000/           200
http://127.0.0.1:3000/community  200
http://127.0.0.1:3000/creator    200
```

## Visual evidence

- `.test-artifacts/ui-audit-20261010/community-1440.png`
- `.test-artifacts/ui-audit-20261010/creator-1440.png`
- `.test-artifacts/ui-audit-20261010/creator-768.png`

The screenshots were captured from the running local Next.js application using Edge headless mode.

## Acceptance mapping

| Requirement | Evidence |
|---|---|
| Shared max width and page padding | `web/app/design-system.css` shared `--page-max` and `--page-padding` |
| Spacing, color, radius, shadow and z-index tokens | `web/app/design-system.css` root token block |
| 40px buttons / 44px controls | shared creator and community control rules |
| Keyboard focus and skip navigation | global focus rule, `skipLink`, `main-content` anchors |
| Drawer keyboard and scroll behavior | Escape handler, body lock, dialog/inert attributes |
| Tablet and mobile reflow | 1024, 768 and 480px media rules |
| Reduced motion | `prefers-reduced-motion` media rule |
| Production compilation | successful Next.js build and TypeScript pass |

No Production Candidate status is asserted.

import { existsSync, renameSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const serverRoutes = resolve("app", "api");
const parkedRoutes = resolve(".static-demo-server-routes");

if (!existsSync(serverRoutes) || existsSync(parkedRoutes)) {
  throw new Error("静态演示构建无法安全隔离 server-only Route Handlers");
}

renameSync(serverRoutes, parkedRoutes);
try {
  const nextCli = resolve("node_modules", "next", "dist", "bin", "next");
  const result = spawnSync(process.execPath, [nextCli, "build"], {
    cwd: process.cwd(),
    env: { ...process.env, STATIC_EXPORT: "true", NEXT_PUBLIC_DEMO_MODE: "true" },
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
} finally {
  renameSync(parkedRoutes, serverRoutes);
}

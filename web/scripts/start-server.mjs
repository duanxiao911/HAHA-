function validateRuntimeConfiguration() {
  const environment = (process.env.HAHA_ENVIRONMENT ?? "development").toLowerCase();
  if (!["development", "staging", "production"].includes(environment)) {
    throw new Error(`不支持的 HAHA_ENVIRONMENT：${environment}`);
  }
  if (["staging", "production"].includes(environment)) {
    if ((process.env.HAHA_COOKIE_SECURE ?? "").toLowerCase() !== "true") {
      throw new Error("staging/production 必须设置 HAHA_COOKIE_SECURE=true");
    }
    if (!process.env.HAHA_INTERNAL_API_URL) {
      throw new Error("staging/production 必须设置 HAHA_INTERNAL_API_URL");
    }
  }
  if (process.env.HAHA_INTERNAL_API_URL) {
    const url = new URL(process.env.HAHA_INTERNAL_API_URL);
    if (!["http:", "https:"].includes(url.protocol) || url.pathname !== "/") {
      throw new Error("HAHA_INTERNAL_API_URL 必须是无路径的 http/https origin");
    }
  }
}

validateRuntimeConfiguration();
await import("./server.js");

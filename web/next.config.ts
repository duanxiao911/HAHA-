import type { NextConfig } from "next";

const isStaticDemo = process.env.STATIC_EXPORT === "true";
const repositoryBasePath = process.env.GITHUB_REPOSITORY?.split("/")[1]
  ? `/${process.env.GITHUB_REPOSITORY.split("/")[1]}`
  : "";

const nextConfig: NextConfig = {
  output: isStaticDemo ? "export" : "standalone",
  basePath: isStaticDemo ? repositoryBasePath : "",
  assetPrefix: isStaticDemo ? repositoryBasePath : "",
  trailingSlash: isStaticDemo,
  poweredByHeader: false,
  reactStrictMode: true,
  headers: isStaticDemo ? undefined : async () => [{
    source: "/:path*",
    headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
    ],
  }],
};

export default nextConfig;

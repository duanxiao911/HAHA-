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
};

export default nextConfig;

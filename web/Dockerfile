ARG NODE_BASE_IMAGE=mcr.microsoft.com/azurelinux/base/nodejs:24@sha256:5583f79d517aff6422b50c8b75b328061cbd2be9ddbc3a14683783952a290b20
FROM ${NODE_BASE_IMAGE} AS dependencies
ARG NPM_REGISTRY=https://registry.npmjs.org
ARG PNPM_VERSION=10.18.3
ENV COREPACK_NPM_REGISTRY=${NPM_REGISTRY}
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable \
    && corepack install --global pnpm@${PNPM_VERSION} \
    && pnpm config set registry "${NPM_REGISTRY}" \
    && pnpm install --frozen-lockfile

FROM ${NODE_BASE_IMAGE} AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
ARG NEXT_PUBLIC_AUTH_MODE=dev
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_AUTH_MODE=$NEXT_PUBLIC_AUTH_MODE
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN ./node_modules/.bin/next build

FROM ${NODE_BASE_IMAGE} AS runner
ENV NODE_ENV=production
WORKDIR /app
COPY --from=builder --chown=65532:65532 /app/.next/standalone ./
COPY --from=builder --chown=65532:65532 /app/.next/static ./.next/static
USER 65532:65532
EXPOSE 3000
CMD ["node", "server.js"]

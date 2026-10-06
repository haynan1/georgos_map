# syntax=docker/dockerfile:1.12

FROM node:24-alpine AS base
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH
RUN npm install --global --no-fund --no-audit pnpm@12.9.1
WORKDIR /app

# ---------------------------------------------------------------------------------------
# Dependencies from the lockfile only; cached until package.json or the lockfile change.
FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile

# ---------------------------------------------------------------------------------------
# Development server; source is bind-mounted by compose.
FROM deps AS dev
COPY . .
RUN chown -R node:node /app
USER node
EXPOSE 5173
CMD ["pnpm", "dev"]

# ---------------------------------------------------------------------------------------
FROM deps AS build
COPY . .
RUN pnpm build

# ---------------------------------------------------------------------------------------
# Production: static files behind unprivileged nginx (runs as uid 101, port 8080).
FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.inc /etc/nginx/snippets/security-headers.inc
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget --quiet --spider http://127.0.0.1:8080/healthz || exit 1

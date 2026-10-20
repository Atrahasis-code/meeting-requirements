# React produces architecture-independent static files. Build with the builder's
# native Node binary; only the final Nginx image needs the target architecture.
FROM --platform=$BUILDPLATFORM node:24-bookworm-slim@sha256:a5f4366e834695d5f363b920c104953a535d3a9864d1bdf74566a0ebe01daee5 AS base
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund && groupadd -g 10001 app && useradd -u 10001 -g app app && chown -R app:app /app
COPY --chown=10001:10001 frontend/ /app/
USER 10001:10001
FROM base AS development
CMD ["npm", "run", "dev"]
FROM base AS test
CMD ["npm", "test"]
FROM base AS build
RUN npm run build
FROM nginx:stable-alpine@sha256:970364228b1e4f932abc22d321932816782cca8a20b85a77552a7cfe9acfb3b5 AS runtime
RUN addgroup -g 10001 app && adduser -D -u 10001 -G app app
COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 10001:10001
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]

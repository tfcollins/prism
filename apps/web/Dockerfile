FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Short git commit, injected into the bundle via Vite `define`. Defaults to
# 'dev' when not supplied; the Makefile deploy target passes the real SHA.
ARG GIT_COMMIT=dev
ENV GIT_COMMIT=$GIT_COMMIT
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80

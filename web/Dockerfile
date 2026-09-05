FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY config.js.template /etc/nginx/templates/config.js.template
COPY docker-entrypoint.d/40-inject-config.sh /docker-entrypoint.d/40-inject-config.sh
RUN chmod +x /docker-entrypoint.d/40-inject-config.sh

EXPOSE 8080

FROM node:22-alpine

# Install Docker CLI (for docker compose commands)
RUN apk add --no-cache docker-cli docker-cli-compose

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY . .

EXPOSE 80

CMD ["node", "server.js"]

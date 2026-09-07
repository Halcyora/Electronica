# Dockerfile for FractalPulse Dashboard (React + Vite)

# Build stage
FROM node:20-slim AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY public/ ./public/
COPY src/ ./src/
COPY vite.config.js index.html ./

RUN npm run build

# Production stage
FROM node:20-slim

WORKDIR /app

# Install serve to run static files
RUN npm install -g serve

# Copy built files from builder
COPY --from=builder /app/dist ./dist

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3000 || exit 1

CMD ["serve", "-s", "dist", "-l", "3000"]

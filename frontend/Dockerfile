# Frontend Dockerfile for FOV Notification Service
# Multi-stage build: Node for building, nginx for serving

# Stage 1: Build the React app
FROM --platform=linux/amd64 node:22-alpine AS builder

WORKDIR /app

# Install dependencies first
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM --platform=linux/amd64 nginx:alpine

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

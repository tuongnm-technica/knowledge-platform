# Stage 1: Build ứng dụng Vite
FROM node:20-alpine AS build-stage

WORKDIR /app

# Chỉ copy file package.json trước để tận dụng Docker Cache cho node_modules
COPY package*.json ./
RUN npm install

# Copy toàn bộ mã nguồn Frontend và chạy lệnh build
COPY . .
RUN npm run build

# Stage 2: Chạy Nginx để phục vụ file tĩnh
FROM nginx:alpine

# Copy cấu hình Nginx custom và kết quả build từ Stage 1
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build-stage /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
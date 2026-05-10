#!/bin/bash

set -e

echo "========================================"
echo "   AI客服系统 - 一键部署脚本"
echo "========================================"

SERVER_IP="47.100.53.133"
USERNAME="root"
PASSWORD="Liaomessi20055810"
DOMAIN="wjhai.cn"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查 sshpass 是否安装
check_sshpass() {
    if ! command -v sshpass &> /dev/null; then
        log_warn "需要安装 sshpass..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y sshpass
        elif command -v yum &> /dev/null; then
            sudo yum install -y sshpass
        elif command -v brew &> /dev/null; then
            brew install sshpass
        else
            log_error "请手动安装 sshpass 或使用 SSH 密钥"
            exit 1
        fi
    fi
}

# 远程执行命令
ssh_exec() {
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$USERNAME@$SERVER_IP" "$1"
}

# 上传文件
scp_upload() {
    sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$1" "$USERNAME@$SERVER_IP:$2"
}

log_info "开始部署 AI客服系统..."

# 1. 安装必要软件
log_info "1. 安装 Docker 和 Docker Compose..."
ssh_exec "apt-get update && apt-get install -y docker.io docker-compose nginx certbot python3-certbot-nginx"

# 2. 启动 Docker 服务
log_info "2. 启动 Docker 服务..."
ssh_exec "systemctl enable docker && systemctl start docker"

# 3. 创建项目目录
log_info "3. 创建项目目录..."
ssh_exec "mkdir -p /var/www/ai-kefu && mkdir -p /opt/ai-kefu"

# 4. 创建 Dockerfile
log_info "4. 创建 Dockerfile..."
ssh_exec "cat > /opt/ai-kefu/Dockerfile << 'EOF'
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/data

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD [\"python\", \"-m\", \"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]
EOF"

# 5. 创建 docker-compose.yml
log_info "5. 创建 docker-compose.yml..."
ssh_exec "cat > /opt/ai-kefu/docker-compose.yml << 'EOF'
version: '3.8'

services:
  backend:
    build:
      context: ./src/backend
      dockerfile: Dockerfile
    container_name: ai-kefu-backend
    ports:
      - \"8000:8000\"
    environment:
      - COZE_API_KEY=\${COZE_API_KEY:-your_api_key_here}
      - COZE_BOT_ID=\${COZE_BOT_ID:-your_bot_id_here}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    networks:
      - ai-kefu-network

  nginx:
    image: nginx:alpine
    container_name: ai-kefu-nginx
    ports:
      - \"80:80\"
      - \"443:443\"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./src/renderer:/usr/share/nginx/html:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - backend
    restart: unless-stopped
    networks:
      - ai-kefu-network

networks:
  ai-kefu-network:
    driver: bridge
EOF"

# 6. 创建 Nginx 配置
log_info "6. 创建 Nginx 配置..."
ssh_exec "cat > /opt/ai-kefu/nginx/nginx.conf << 'EOF'
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '\$remote_addr - \$remote_user [\$time_local] \"\$request\" '
                    '\$status \$body_bytes_sent \"\$http_referer\" '
                    '\"\$http_user_agent\" \"\$http_x_forwarded_for\"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json application/javascript 
               application/xml application/xml+rss text/javascript;

    add_header X-Frame-Options \"SAMEORIGIN\" always;
    add_header X-Content-Type-Options \"nosniff\" always;
    add_header X-XSS-Protection \"1; mode=block\" always;

    client_max_body_size 10M;

    upstream backend {
        server backend:8000;
        keepalive 32;
    }

    server {
        listen 80;
        server_name $DOMAIN www.$DOMAIN;

        root /usr/share/nginx/html;
        index index.html;

        location / {
            try_files \$uri \$uri/ /index.html;
        }

        location /api/ {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        location /health {
            proxy_pass http://backend;
            access_log off;
        }

        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf)$ {
            expires 30d;
            add_header Cache-Control \"public, immutable\";
        }
    }
}
EOF"

# 7. 克隆项目
log_info "7. 克隆 GitHub 项目..."
ssh_exec "cd /opt/ai-kefu && git clone https://github.com/200510wjh/ai-kefu-opensource.git . || echo '项目已存在，跳过克隆'"

# 8. 复制 requirements.txt
log_info "8. 复制后端文件..."
ssh_exec "mkdir -p /opt/ai-kefu/src/backend"
ssh_exec "cp /opt/ai-kefu/src/backend/requirements.txt /opt/ai-kefu/requirements.txt 2>/dev/null || echo 'requirements.txt not found'"

# 9. 构建和启动
log_info "9. 构建并启动 Docker 容器..."
ssh_exec "cd /opt/ai-kefu && docker-compose build && docker-compose up -d"

# 10. 配置 SSL (Let's Encrypt)
log_info "10. 配置 SSL 证书..."
ssh_exec "certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN || echo 'SSL 配置可选，稍后可手动执行'"

# 11. 配置防火墙
log_info "11. 配置防火墙..."
ssh_exec "ufw allow 80/tcp && ufw allow 443/tcp && ufw reload || echo '防火墙配置跳过'"

log_info "========================================"
log_info "   部署完成!"
log_info "========================================"
log_info "访问地址: https://$DOMAIN"
log_info "API 地址: https://$DOMAIN/api/"
log_info ""
log_warn "请配置你的扣子 API Key:"
log_info "  1. 编辑 /opt/ai-kefu/.env 文件"
log_info "  2. 添加: COZE_API_KEY=你的APIKey"
log_info "  3. 重启: cd /opt/ai-kefu && docker-compose restart"
log_info ""
log_info "管理命令:"
log_info "  查看日志: docker-compose logs -f"
log_info "  停止服务: docker-compose down"
log_info "  重启服务: docker-compose restart"

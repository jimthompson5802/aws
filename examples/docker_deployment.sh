#!/bin/bash
# Example user data script: Docker Application Deployment
# This script sets up Docker and deploys a containerized application

# Update system packages
yum update -y

# Install Docker
yum install -y docker
systemctl start docker
systemctl enable docker

# Add ec2-user to docker group
usermod -a -G docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create application directory
mkdir -p /opt/app
cd /opt/app

# Clone application repository
git clone https://github.com/example/docker-app.git .

# Set up environment variables
cat << 'EOF' > .env
NODE_ENV=production
PORT=3000
DATABASE_URL=sqlite:///data/app.db
EOF

# Create docker-compose.yml for the application
cat << 'EOF' > docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "80:3000"
    environment:
      - NODE_ENV=production
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - web
    restart: unless-stopped
EOF

# Create nginx configuration
cat << 'EOF' > nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream app {
        server web:3000;
    }

    server {
        listen 80;
        server_name _;
        
        location / {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }
}
EOF

# Create data directory
mkdir -p data

# Change ownership
chown -R ec2-user:ec2-user /opt/app

# Build and start the application
docker-compose up -d

# Create systemd service to manage docker-compose
cat << 'EOF' > /etc/systemd/system/docker-app.service
[Unit]
Description=Docker App
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/app
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# Enable the service
systemctl daemon-reload
systemctl enable docker-app

echo "Docker application deployment completed successfully!"
echo "Application is running on port 80"

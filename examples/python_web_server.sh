#!/bin/bash
# Example user data script: Python Web Server Setup
# This script sets up a Python web server with Flask

# Update system packages
yum update -y

# Install Python 3 and development tools
yum install -y python3 python3-pip git

# Create application directory
mkdir -p /opt/webapp
cd /opt/webapp

# Clone a sample web application repository
git clone https://github.com/example/flask-app.git app
cd app

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install flask gunicorn boto3 requests

# Set up environment variables
echo "export FLASK_APP=app.py" >> /etc/environment
echo "export FLASK_ENV=production" >> /etc/environment
echo "export PORT=5000" >> /etc/environment

# Create systemd service for the web application
cat << 'EOF' > /etc/systemd/system/webapp.service
[Unit]
Description=Flask Web Application
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/webapp/app
Environment=PATH=/opt/webapp/app/venv/bin
ExecStart=/opt/webapp/app/venv/bin/gunicorn --bind 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start and enable the web application service
systemctl daemon-reload
systemctl enable webapp
systemctl start webapp

# Install and configure nginx as reverse proxy
yum install -y nginx

cat << 'EOF' > /etc/nginx/conf.d/webapp.conf
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

# Start and enable nginx
systemctl enable nginx
systemctl start nginx

echo "Python web server setup completed successfully!"

#!/bin/bash
# Example user data script: Basic Development Environment
# This script sets up a basic development environment with common tools

# Update system packages
yum update -y

# Install development tools
yum groupinstall -y "Development Tools"
yum install -y git curl wget htop tree vim nano

# Install Node.js and npm
curl -sL https://rpm.nodesource.com/setup_18.x | bash -
yum install -y nodejs

# Install Python 3 and pip
yum install -y python3 python3-pip

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install

# Install Docker
yum install -y docker
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Create development workspace
mkdir -p /home/ec2-user/workspace
cd /home/ec2-user/workspace

# Set up Python virtual environment
python3 -m venv python-env
source python-env/bin/activate
pip install --upgrade pip
pip install boto3 requests flask django fastapi

# Install common Node.js packages globally
npm install -g npm@latest
npm install -g yarn pm2 nodemon

# Set up Git configuration (placeholder - should be customized)
sudo -u ec2-user git config --global user.name "Developer"
sudo -u ec2-user git config --global user.email "developer@example.com"
sudo -u ec2-user git config --global init.defaultBranch main

# Create useful aliases
cat << 'EOF' >> /home/ec2-user/.bashrc

# Custom aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias ..='cd ..'
alias ...='cd ../..'
alias grep='grep --color=auto'
alias docker-ps='docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
alias python-activate='source /home/ec2-user/workspace/python-env/bin/activate'

# Environment variables
export WORKSPACE=/home/ec2-user/workspace
export PATH=$PATH:/home/ec2-user/.local/bin
EOF

# Set up zsh (optional)
yum install -y zsh
chsh -s /bin/zsh ec2-user

# Install oh-my-zsh for ec2-user
sudo -u ec2-user sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

# Configure oh-my-zsh
sudo -u ec2-user sed -i 's/ZSH_THEME="robbyrussell"/ZSH_THEME="agnoster"/' /home/ec2-user/.zshrc
sudo -u ec2-user sed -i 's/plugins=(git)/plugins=(git aws docker python pip node npm)/' /home/ec2-user/.zshrc

# Add custom aliases to zsh
cat << 'EOF' >> /home/ec2-user/.zshrc

# Custom aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias ..='cd ..'
alias ...='cd ../..'
alias grep='grep --color=auto'
alias docker-ps='docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
alias python-activate='source /home/ec2-user/workspace/python-env/bin/activate'

# Environment variables
export WORKSPACE=/home/ec2-user/workspace
export PATH=$PATH:/home/ec2-user/.local/bin
EOF

# Change ownership of workspace to ec2-user
chown -R ec2-user:ec2-user /home/ec2-user/workspace
chown -R ec2-user:ec2-user /home/ec2-user/.zshrc
chown -R ec2-user:ec2-user /home/ec2-user/.oh-my-zsh

# Install code-server (VS Code in browser)
curl -fsSL https://code-server.dev/install.sh | sh

# Configure code-server
mkdir -p /home/ec2-user/.config/code-server
cat << 'EOF' > /home/ec2-user/.config/code-server/config.yaml
bind-addr: 0.0.0.0:8080
auth: none
password: 
cert: false
EOF

# Create systemd service for code-server
cat << 'EOF' > /etc/systemd/system/code-server.service
[Unit]
Description=code-server
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/workspace
ExecStart=/usr/bin/code-server
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start and enable code-server
systemctl daemon-reload
systemctl enable code-server
systemctl start code-server

chown -R ec2-user:ec2-user /home/ec2-user/.config

echo "Development environment setup completed successfully!"
echo "Code Server is running on port 8080"
echo "Python virtual environment: /home/ec2-user/workspace/python-env"
echo "Workspace directory: /home/ec2-user/workspace"

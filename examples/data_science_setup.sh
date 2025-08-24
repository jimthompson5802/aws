#!/bin/bash
# Example user data script: Data Science Environment Setup
# This script sets up a comprehensive data science environment with Jupyter

# Update system packages
yum update -y

# Install system dependencies
yum groupinstall -y "Development Tools"
yum install -y python3 python3-pip git htop curl wget

# Create data science workspace
mkdir -p /opt/datascience
cd /opt/datascience

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install data science packages
pip install --upgrade pip
pip install jupyter jupyterlab
pip install pandas numpy scipy matplotlib seaborn
pip install scikit-learn tensorflow pytorch
pip install boto3 awscli
pip install plotly dash streamlit

# Clone sample data science projects
git clone https://github.com/example/data-science-projects.git projects

# Set up Jupyter configuration
mkdir -p /home/ec2-user/.jupyter
cat << 'EOF' > /home/ec2-user/.jupyter/jupyter_notebook_config.py
c.NotebookApp.ip = '0.0.0.0'
c.NotebookApp.port = 8888
c.NotebookApp.open_browser = False
c.NotebookApp.token = ''
c.NotebookApp.password = ''
c.NotebookApp.allow_root = True
EOF

# Change ownership to ec2-user
chown -R ec2-user:ec2-user /opt/datascience
chown -R ec2-user:ec2-user /home/ec2-user/.jupyter

# Create systemd service for Jupyter
cat << 'EOF' > /etc/systemd/system/jupyter.service
[Unit]
Description=Jupyter Lab
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/datascience
Environment=PATH=/opt/datascience/venv/bin
ExecStart=/opt/datascience/venv/bin/jupyter lab --config=/home/ec2-user/.jupyter/jupyter_notebook_config.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start and enable Jupyter service
systemctl daemon-reload
systemctl enable jupyter
systemctl start jupyter

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Set up environment variables for data science
cat << 'EOF' >> /etc/environment
PYTHONPATH=/opt/datascience
JUPYTER_CONFIG_DIR=/home/ec2-user/.jupyter
DATA_DIR=/opt/datascience/data
MODELS_DIR=/opt/datascience/models
EOF

# Create data and models directories
mkdir -p /opt/datascience/data
mkdir -p /opt/datascience/models
chown -R ec2-user:ec2-user /opt/datascience

echo "Data science environment setup completed successfully!"
echo "Jupyter Lab is running on port 8888"

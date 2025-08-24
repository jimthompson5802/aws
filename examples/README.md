# User Data Script Examples

This directory contains pre-built user data scripts for common AWS EC2 instance customization scenarios. These scripts automate the setup and configuration of various software environments and applications on your EC2 instances.

## Available Scripts

### 1. `python_web_server.sh`
**Purpose**: Sets up a complete Python web server environment with Flask and nginx

**Features**:
- Updates system packages
- Installs Python 3 and development tools
- Clones a sample Flask application from Git
- Creates Python virtual environment
- Installs Flask, Gunicorn, and other dependencies
- Configures systemd service for the web application
- Sets up nginx as reverse proxy
- Starts all services automatically

**Use Case**: Web applications, REST APIs, microservices

### 2. `data_science_setup.sh`
**Purpose**: Creates a comprehensive data science environment with Jupyter Lab

**Features**:
- Installs Python 3 and development tools
- Sets up data science packages (pandas, numpy, scikit-learn, tensorflow, etc.)
- Configures Jupyter Lab with remote access
- Installs AWS CLI v2
- Creates data and models directories
- Sets up systemd service for Jupyter

**Use Case**: Data analysis, machine learning, research environments

**Access**: Jupyter Lab will be available on port 8888

### 3. `docker_deployment.sh`
**Purpose**: Sets up Docker and deploys containerized applications

**Features**:
- Installs Docker and Docker Compose
- Configures Docker service
- Clones application repository
- Sets up docker-compose configuration
- Configures nginx for containerized apps
- Creates systemd service for application management

**Use Case**: Containerized applications, microservices, CI/CD deployments

### 4. `database_setup.sh`
**Purpose**: Installs and configures MySQL database server

**Features**:
- Installs MySQL 8.0
- Performs secure installation
- Creates application database and user
- Configures remote connections
- Sets up automated backup scripts
- Creates monitoring scripts
- Schedules daily backups via cron

**Use Case**: Database servers, application backends

**Security**: Uses strong passwords and encrypted connections

### 5. `dev_environment.sh`
**Purpose**: Creates a complete development environment

**Features**:
- Installs development tools and compilers
- Sets up Node.js, Python, and AWS CLI
- Installs Docker
- Configures Git with default settings
- Installs VS Code Server for remote development
- Sets up zsh with oh-my-zsh
- Creates useful aliases and environment variables

**Use Case**: Development workstations, CI/CD agents, build servers

**Access**: VS Code Server available on port 8080

## Usage

### In YAML Specification (Script Path)
```yaml
instances:
  - name: "my-server"
    instance_type: "t3.micro"
    ami_id: "ami-0c02fb55956c7d316"
    user_data:
      script_path: "examples/python_web_server.sh"
```

### In YAML Specification (Inline Script)
```yaml
instances:
  - name: "my-server"
    instance_type: "t3.micro"
    ami_id: "ami-0c02fb55956c7d316"
    user_data:
      inline_script: |
        #!/bin/bash
        yum update -y
        yum install -y docker
        systemctl start docker
```

## Customization

You can modify these scripts to suit your specific needs:

1. **Copy the script**: Create a copy of the script you want to modify
2. **Edit variables**: Update package versions, repository URLs, passwords, etc.
3. **Add custom steps**: Include your own installation or configuration steps
4. **Update paths**: Modify the `script_path` in your YAML specification

## Security Considerations

- **Passwords**: The example scripts use placeholder passwords. **Always change these in production!**
- **SSH Keys**: Configure proper SSH key access for secure connections
- **Firewall**: Ensure security groups are properly configured for the services
- **Updates**: Regularly update the scripts to use latest package versions
- **Secrets**: Never hardcode sensitive information in scripts; use AWS Secrets Manager or Parameter Store

## Logging

All scripts include comprehensive logging:
- Execution logs are captured in `/var/log/user-data-execution.log`
- Individual service logs are available via `journalctl`
- You can monitor execution with: `python script.py monitor --spec your-spec.yaml`

## Troubleshooting

### Common Issues

1. **Script fails to execute**: Check the script has proper shebang (`#!/bin/bash`)
2. **Package installation fails**: Ensure the AMI has internet access
3. **Service won't start**: Check logs with `journalctl -u service-name`
4. **Permissions issues**: Ensure proper file ownership and permissions

### Debugging

1. **SSH into instance**: Use your key pair to connect
2. **Check user data logs**: `sudo cat /var/log/user-data-execution.log`
3. **Check cloud-init logs**: `sudo cat /var/log/cloud-init-output.log`
4. **Monitor execution**: Use the monitoring command from the main script

## Contributing

To contribute new example scripts:

1. Create a new `.sh` file in this directory
2. Follow the existing pattern with logging wrapper
3. Include comprehensive comments
4. Test thoroughly with different instance types
5. Update this README with script description

## License

These example scripts are provided as-is for educational and automation purposes. Please review and test thoroughly before using in production environments.

# Examples Directory

This directory contains both user data scripts and YAML specification examples for AWS EC2 instance provisioning and management. The scripts automate the setup and configuration of various software environments, while the YAML files demonstrate different configuration patterns.

## User Data Scripts

## Available User Data Scripts

### 1. `python_web_server.sh`
**Purpose**: Sets up a complete Python web server environment with Flask and Gunicorn

**Features**:
- Updates system packages  
- Installs Python 3, pip, and Git
- Creates application directory at `/opt/webapp`
- Clones a sample Flask application from Git
- Creates Python virtual environment
- Installs Flask, Gunicorn, and boto3 packages
- Configures systemd service for the web application
- Starts application on port 5000

**Use Case**: Web applications, REST APIs, Flask-based services

### 2. `data_science_setup.sh`
**Purpose**: Creates a comprehensive data science environment with Jupyter Lab

**Features**:
- Installs development tools and Python 3
- Sets up data science packages (pandas, numpy, scikit-learn, tensorflow, pytorch, etc.)
- Configures Jupyter Lab with remote access (port 8888)
- Installs AWS CLI v2 and boto3
- Creates data science workspace at `/opt/datascience`
- Sets up systemd service for Jupyter
- Includes plotly, dash, and streamlit for visualization

**Use Case**: Data analysis, machine learning, research environments
**Access**: Jupyter Lab available on port 8888 (no authentication configured)

### 3. `docker_deployment.sh`
**Purpose**: Sets up Docker environment and deploys containerized applications

**Features**:
- Installs Docker and Docker Compose
- Configures Docker service and adds ec2-user to docker group
- Creates application directory at `/opt/app`
- Clones application repository from Git
- Sets up docker-compose configuration with nginx
- Configures environment variables for production
- Creates systemd service for application management

**Use Case**: Containerized applications, microservices, Docker-based deployments

### 4. `database_setup.sh`
**Purpose**: Installs and configures MySQL 8.0 database server

**Features**:
- Installs MySQL 8.0 server
- Performs secure installation with strong passwords
- Creates application database (`appdb`) and user (`appuser`)
- Configures remote connections (bind-address = 0.0.0.0)
- Sets up automated backup scripts
- Installs AWS CLI for backup management
- Creates monitoring and backup automation

**Use Case**: Database servers, application backends
**Security**: Uses strong passwords - **change defaults in production!**

### 5. `dev_environment.sh`
**Purpose**: Creates a complete development environment with multiple tools

**Features**:
- Installs development tools and compilers ("Development Tools" group)
- Sets up Node.js 18.x, Python 3, and AWS CLI v2
- Installs Docker and adds ec2-user to docker group
- Configures Git with placeholder settings
- Creates development workspace at `/home/ec2-user/workspace`
- Sets up Python virtual environment and Node.js packages
- Installs common packages (boto3, flask, django, fastapi, yarn, pm2)
- Creates useful bash aliases

**Use Case**: Development workstations, CI/CD agents, build servers

## YAML Configuration Examples

### Basic Examples
- **`example.yaml`**: Simple instance with EBS volume
- **`example_spec.yaml`**: Comprehensive example with all features
- **`example_connection_info.yaml`**: Minimal example for connection testing

### Authentication Examples  
- **`example_with_profile.yaml`**: AWS profile-based authentication
- **`example_with_iam_role.yaml`**: IAM instance profile assignment

### Advanced Features
- **`example_with_idle_shutdown.yaml`**: CloudWatch-based auto-shutdown for cost optimization
- **`example_with_mount_points.yaml`**: Automatic EBS volume mounting configuration

## Usage Examples

### Using a User Data Script (Script Path)
```yaml
instances:
  - name: "my-web-server"
    instance_type: "t3.micro"
    ami_id: "ami-0c02fb55956c7d316"
    key_name: "my-key-pair"
    user_data:
      script_path: "examples/python_web_server.sh"
```

### Using Inline User Data Script
```yaml
instances:
  - name: "my-server"
    instance_type: "t3.micro"
    ami_id: "ami-0c02fb55956c7d316"
    key_name: "my-key-pair"
    user_data:
      inline_script: |
        #!/bin/bash
        yum update -y
        yum install -y docker
        systemctl start docker
        systemctl enable docker
```

### Using AWS Profile Authentication
```yaml
profile: "my-aws-profile"

instances:
  - name: "my-server"
    instance_type: "t3.micro"
    ami_id: "ami-0c02fb55956c7d316"
    key_name: "my-key-pair"
```

### Configuring Auto-Shutdown for Cost Optimization
```yaml
instances:
  - name: "development-server"
    instance_type: "t3.medium"
    ami_id: "ami-0c02fb55956c7d316"
    market_type: "spot"
    idle_shutdown:
      cpu_threshold: 10.0          # Stop when CPU < 10%
      evaluation_minutes: 20       # Evaluate for 20 minutes
      action: "stop"               # "stop" or "terminate"
```

### Automatic Volume Mounting
```yaml
instances:
  - name: "database-server"
    instance_type: "t3.medium"
    ami_id: "ami-0c02fb55956c7d316"
    volumes:
      - size: 100
        type: "gp3"
        device: "/dev/sdf"
        mount_point: "/var/lib/mysql"
        filesystem: "ext4"
        encrypted: true
```

## Available Example Files

The following YAML files demonstrate different configuration patterns:

| File | Purpose |
|------|---------|
| `example.yaml` | Basic instance with EBS volume |
| `example_spec.yaml` | Comprehensive example with all available features |
| `example_connection_info.yaml` | Minimal configuration for connection testing |
| `example_with_profile.yaml` | AWS profile-based authentication |
| `example_with_iam_role.yaml` | IAM instance profile assignment |
| `example_with_idle_shutdown.yaml` | CloudWatch idle shutdown configuration |
| `example_with_mount_points.yaml` | Automatic EBS volume mounting |

## Quick Start

1. **Choose a template**: Copy one of the example YAML files that matches your use case
2. **Update values**: Replace placeholder values (AMI IDs, key pairs, security groups, etc.)
3. **Select user data**: Choose an appropriate script from the available options or write your own
4. **Deploy**: Run `python script.py provision --spec your-spec.yaml`

## Running the Examples

```bash
# Provision using a basic example
python script.py provision --spec examples/example.yaml

# Use a specific AWS profile
python script.py provision --spec examples/example_with_profile.yaml --profile my-profile

# Monitor instance status
python script.py monitor --spec examples/example.yaml

# Get connection information
python script.py connect --spec examples/example_connection_info.yaml

# Clean up resources
python script.py destroy --spec examples/example.yaml
```

## Customization

### Modifying User Data Scripts

You can customize the scripts to suit your specific needs:

1. **Copy the script**: Create a copy of the script you want to modify
2. **Edit variables**: Update package versions, repository URLs, passwords, etc.
3. **Add custom steps**: Include your own installation or configuration steps
4. **Update YAML**: Modify the `script_path` in your YAML specification

### Creating Custom YAML Configurations

1. **Start with a template**: Copy the most relevant example file
2. **Update identifiers**: Replace AMI IDs, key pairs, security groups with your values
3. **Customize tags**: Add your own tags for organization and billing
4. **Configure networking**: Set appropriate subnets and security groups
5. **Add volumes**: Define EBS volumes with appropriate sizes and types

## Security Considerations

- **Passwords**: The example scripts use placeholder passwords. **Always change these in production!**
  - MySQL root password: `SecurePassword123!`
  - MySQL app user password: `AppPassword123!`
- **SSH Keys**: Configure proper SSH key access for secure connections
- **Firewall**: Ensure security groups are properly configured for the services
- **Updates**: Regularly update the scripts to use latest package versions
- **Secrets**: Never hardcode sensitive information in scripts; use AWS Secrets Manager or Parameter Store
- **Jupyter Security**: The data science setup has no authentication configured - secure it for production use
- **Remote Access**: Database and other services are configured for remote access - restrict as needed

## Port Reference

The following ports are used by the example scripts:

| Service | Port | Script |
|---------|------|--------|
| Flask Web Server | 5000 | `python_web_server.sh` |
| Jupyter Lab | 8888 | `data_science_setup.sh` |
| Docker Applications | 80 | `docker_deployment.sh` |
| MySQL Database | 3306 | `database_setup.sh` |

Ensure your security groups allow access to the appropriate ports.

## Logging and Monitoring

All scripts include comprehensive logging:
- User data execution logs are in `/var/log/cloud-init-output.log`
- Individual service logs are available via `journalctl -u service-name`
- Monitor instance status: `python script.py monitor --spec your-spec.yaml`
- Get connection information: `python script.py connect --spec your-spec.yaml`

## Important File Locations

| Purpose | Location | Scripts |
|---------|----------|---------|
| Web Application | `/opt/webapp` | `python_web_server.sh` |
| Data Science Workspace | `/opt/datascience` | `data_science_setup.sh` |
| Docker Applications | `/opt/app` | `docker_deployment.sh` |
| Development Workspace | `/home/ec2-user/workspace` | `dev_environment.sh` |
| MySQL Backups | `/opt/backups` | `database_setup.sh` |
| Jupyter Config | `/home/ec2-user/.jupyter` | `data_science_setup.sh` |

## Troubleshooting

### Common Issues

1. **Script fails to execute**: Check the script has proper shebang (`#!/bin/bash`)
2. **Package installation fails**: Ensure the instance has internet access and proper routes
3. **Service won't start**: Check logs with `journalctl -u service-name`
4. **Permissions issues**: Ensure proper file ownership and permissions
5. **Git clone fails**: Check if the repository URLs in scripts are accessible
6. **MySQL connection fails**: Verify security group allows port 3306
7. **Jupyter not accessible**: Check security group allows port 8888

### Debugging Steps

1. **SSH into instance**: Use your key pair to connect
2. **Check cloud-init logs**: `sudo cat /var/log/cloud-init-output.log`
3. **Check specific service status**: `sudo systemctl status service-name`
4. **Monitor execution**: Use `python script.py monitor --spec your-spec.yaml`
5. **Verify security groups**: Ensure required ports are open
6. **Check disk space**: Use `df -h` to verify adequate storage

### Log Locations

- **Cloud-init output**: `/var/log/cloud-init-output.log`
- **System messages**: `/var/log/messages`
- **Service logs**: `journalctl -u service-name -f`
- **MySQL logs**: `/var/log/mysqld.log`
- **Docker logs**: `docker logs container-name`

## Contributing

### Adding New User Data Scripts

To contribute new example scripts:

1. Create a new `.sh` file in this directory
2. Follow the existing pattern:
   - Include proper shebang (`#!/bin/bash`)
   - Add descriptive comments
   - Use proper error handling
   - Include systemd service creation if applicable
3. Test thoroughly with different instance types and AMIs
4. Update this README with script description
5. Add corresponding YAML example if needed

### Adding New YAML Examples

1. Create descriptive filename (e.g., `example_with_feature.yaml`)
2. Include comprehensive comments explaining each section
3. Use realistic but clearly placeholder values
4. Test the configuration works as expected
5. Update the examples table in this README

### Testing Guidelines

- Test scripts on fresh instances to ensure they work from clean state
- Verify all services start correctly and are accessible
- Check that security groups and networking work as expected
- Ensure scripts are idempotent where possible

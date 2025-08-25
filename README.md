# AWS Compute and Storage Automation

This project automates the provisioning of AWS EC2 instances and associated storage volumes based on YAML specifications.

## Features

- **Idempotent Operations**: Safely run multiple times without creating duplicates
- **Rollback Support**: Automatic cleanup on failure
- **Spot Instance Support**: Cost optimization with spot instances
- **EBS Volume Management**: Create and attach additional storage
- **User Data Script Support**: Automate instance customization with bash scripts
- **CloudWatch Idle Shutdown**: Automatically stop/terminate idle instances to save costs
- **Script Monitoring**: Monitor user data script execution and retrieve logs
- **Example Scripts**: Pre-built scripts for common scenarios (web servers, databases, etc.)
- **Comprehensive Logging**: Detailed logs for debugging and auditing

## Requirements

- Python 3.7+
- boto3
- PyYAML
- AWS credentials configured

## Installation

```bash
pip install boto3 PyYAML
```

## Usage

### Create Resources
```bash
python script.py create --spec example.yaml --region us-east-1
```

### Delete Resources
```bash
python script.py delete --spec example.yaml --region us-east-1
```

### Monitor User Data Execution
```bash
python script.py monitor --spec example.yaml --region us-east-1
```

### Monitor CloudWatch Alarms
```bash
python script.py monitor-alarms --spec example.yaml --region us-east-1
```

### Using AWS Profiles
```bash
# Use a specific AWS profile
python script.py create --spec example.yaml --profile my-profile

# Profile can also be specified in the YAML file itself
```

### Dry Run
```bash
python script.py create --spec example.yaml --dry-run
```

## Configuration

Create a YAML specification file with your desired infrastructure:

```yaml
# Optional: AWS profile for authentication
profile: "my-aws-profile"

instances:
  - name: "web-server"
    instance_type: "t3.micro"
    ami_id: "ami-0c55b159cbfafe1d0"
    key_name: "my-key"
    security_groups: ["sg-12345"]
    user_data:  # Optional: Automate instance setup
      script_path: "examples/python_web_server.sh"
    volumes:
      - size: 20
        type: "gp3"
        device: "/dev/sdf"
```

## User Data Scripts

The script supports two ways to specify user data for instance customization:

### Using Script Files
```yaml
user_data:
  script_path: "path/to/your/script.sh"
```

### Using Inline Scripts
```yaml
user_data:
  inline_script: |
    #!/bin/bash
    yum update -y
    yum install -y docker
    systemctl start docker
```

## CloudWatch Idle Shutdown

The script supports automatic shutdown of EC2 instances when they are idle using CloudWatch alarms. This feature helps optimize costs by stopping or terminating instances that are not being actively used.

### Configuration

```yaml
instances:
  - name: "development-server"
    instance_type: "t3.medium"
    ami_id: "ami-0c02fb55956c7d316"
    # ... other configuration ...
    idle_shutdown:
      cpu_threshold: 10.0          # Stop when CPU < 10%
      evaluation_minutes: 15       # For 15 minutes continuously
      action: "stop"               # "stop" or "terminate"
```

### Idle Shutdown Parameters

- `cpu_threshold`: CPU utilization threshold (0-100). Instance will be stopped/terminated when CPU falls below this percentage
- `evaluation_minutes`: Number of minutes the CPU must remain below the threshold before taking action
- `action`: Action to take when idle condition is met:
  - `"stop"`: Stop the instance (can be restarted later, preserves instance store)
  - `"terminate"`: Terminate the instance (permanently destroys the instance)

### How It Works

1. When an instance is created, a CloudWatch alarm is automatically created
2. The alarm monitors CPU utilization every 5 minutes
3. If CPU stays below the threshold for the specified duration, the alarm triggers
4. The instance is automatically stopped or terminated based on the configured action
5. When deleting resources, associated CloudWatch alarms are automatically removed

### Use Cases

- **Development environments**: Automatically stop development instances after hours
- **Batch processing**: Terminate instances when jobs complete
- **Cost optimization**: Reduce costs for underutilized instances
- **Spot instances**: Automatic cleanup for cost-sensitive workloads

### Example Configurations

```yaml
# Conservative shutdown for production workloads
idle_shutdown:
  cpu_threshold: 5.0
  evaluation_minutes: 30
  action: "stop"

# Aggressive shutdown for development/testing
idle_shutdown:
  cpu_threshold: 15.0
  evaluation_minutes: 10
  action: "terminate"

# No idle shutdown (omit the idle_shutdown section entirely)
```

**Note**: CloudWatch alarms are automatically cleaned up when instances are terminated through the script's delete command.

## Example Scripts

The `examples/` directory contains pre-built scripts for common scenarios:

- **`python_web_server.sh`** - Complete Python Flask web server with nginx
- **`data_science_setup.sh`** - Jupyter Lab and data science environment
- **`docker_deployment.sh`** - Docker containerized application deployment  
- **`database_setup.sh`** - MySQL database server with automated backups
- **`dev_environment.sh`** - Development environment with VS Code server

## AWS Credentials

The script supports multiple methods for AWS authentication:

### Method 1: Environment Variables
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### Method 2: AWS CLI Profile
```bash
# Configure a profile
aws configure --profile my-profile

# Use the profile via command line
python script.py create --spec example.yaml --profile my-profile
```

### Method 3: YAML Specification Profile
```yaml
# Add profile to your YAML specification
profile: "my-aws-profile"

instances:
  - name: "web-server"
    instance_type: "t3.micro"
    # ... rest of configuration
```

### Method 4: IAM Roles
When running on EC2 instances, IAM roles are automatically used.

### Profile Precedence
1. Command line `--profile` argument (highest priority)
2. `profile` field in YAML specification  
3. Default AWS credentials (environment variables or default profile)
4. IAM roles (when running on EC2)

## License

MIT License

- `name`: Unique name for the instance (used for tagging and idempotency)
- `instance_type`: EC2 instance type (e.g., t3.micro, m5.large)
- `ami_id`: AMI ID to launch (must be valid for your chosen region)

#### Optional Fields

- `market_type`: "on-demand" (default) or "spot"
- `spot_price`: Maximum price for spot instances (string)
- `key_name`: EC2 Key Pair name for SSH access
- `security_groups`: List of Security Group IDs
- `subnet_id`: Subnet ID for VPC deployment
- `tags`: List of custom tags (Key/Value pairs)
- `volumes`: List of additional EBS volumes

#### Volume Configuration

```yaml
volumes:
  - size: 20              # Size in GB (required)
    type: "gp3"           # Volume type: gp2, gp3, io1, io2, st1, sc1
    device: "/dev/sdf"    # Device name
    iops: 3000           # IOPS (for gp3, io1, io2)
    encrypted: true      # Enable encryption
```

## Usage

### Creating Resources

```bash
# Create resources from specification
python script.py create --spec example_spec.yaml

# Create resources in a specific region
python script.py create --spec example_spec.yaml --region us-west-2

# Dry run (preview what will be created)
python script.py create --spec example_spec.yaml --dry-run
```

### Deleting Resources

```bash
# Delete resources matching the specification
python script.py delete --spec example_spec.yaml

# Delete resources in a specific region
python script.py delete --spec example_spec.yaml --region us-west-2
```

### Monitoring User Data Execution

```bash
# Monitor user data script execution for all instances
python script.py monitor --spec example_spec.yaml

# Monitor in a specific region
python script.py monitor --spec example_spec.yaml --region us-west-2
```

### Command Line Options

- `action`: Required. One of "create", "delete", "monitor", or "monitor-alarms"
- `--spec, -s`: Required. Path to the YAML specification file
- `--region, -r`: Optional. AWS region (default: us-east-1)
- `--profile, -p`: Optional. AWS profile name to use for authentication
- `--dry-run`: Optional. Show what would be done without executing (create/delete only)

## Examples

### Simple Web Server

```yaml
instances:
  - name: "web-server"
    instance_type: "t3.micro"
    ami_id: "ami-0c02fb55956c7d316"
    key_name: "my-keypair"
    security_groups:
      - "sg-web-server"
```

### Spot Instance with Storage

```yaml
instances:
  - name: "batch-processor"
    instance_type: "c5.large"
    ami_id: "ami-0c02fb55956c7d316"
    market_type: "spot"
    spot_price: "0.05"
    volumes:
      - size: 100
        type: "gp3"
        device: "/dev/sdf"
        encrypted: true
```

### Multiple Servers with Different Configurations

```yaml
instances:
  - name: "web-server"
    instance_type: "t3.small"
    ami_id: "ami-0c02fb55956c7d316"
    market_type: "on-demand"
    
  - name: "worker-node"
    instance_type: "m5.large"
    ami_id: "ami-0c02fb55956c7d316"
    market_type: "spot"
    spot_price: "0.10"
    volumes:
      - size: 50
        type: "gp3"
        device: "/dev/sdf"
```

## Logging

The script creates detailed logs in two places:
- Console output (INFO level and above)
- Log file: `aws_automation.log` (all levels)

Log entries include timestamps, log levels, and detailed messages about all operations.

## Error Handling and Rollback

If any error occurs during resource creation, the script will automatically:
1. Log the error with details
2. Begin rollback process
3. Delete any partially created resources
4. Exit with error status

This ensures you don't have orphaned resources in case of failures.

## Idempotency

The script checks for existing resources before creating new ones. If instances with the same name (tag) already exist, the script will skip creation and report the existing resources.

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure your AWS credentials have the required permissions
2. **AMI Not Found**: Verify the AMI ID is valid for your chosen region
3. **Subnet/Security Group Not Found**: Ensure the specified resources exist in your VPC
4. **Instance Limit Exceeded**: Check your EC2 service limits

### Debug Mode

For additional debugging information, check the `aws_automation.log` file which contains detailed logs of all operations.

## Testing

Run the test suite to verify functionality:

```bash
pytest tests/
```

Note: The current tests are minimal and focus on the date utility function. For comprehensive testing of AWS functionality, you would need additional test files with proper AWS mocking.

## Security Considerations

- Never commit AWS credentials to version control
- Use IAM roles with minimal required permissions
- Enable EBS encryption for sensitive data
- Regularly review and rotate access keys
- Use VPC security groups to restrict network access

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is provided as-is for educational and automation purposes. Please review and test thoroughly before using in production environments.



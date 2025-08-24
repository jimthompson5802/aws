# AWS Compute and Storage Automation

This project automates the provisioning of AWS EC2 instances and associated storage volumes based on YAML specifications.

## Features

- **Idempotent Operations**: Safely run multiple times without creating duplicates
- **Rollback Support**: Automatic cleanup on failure
- **Spot Instance Support**: Cost optimization with spot instances
- **EBS Volume Management**: Create and attach additional storage
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

### Dry Run
```bash
python script.py create --spec example.yaml --dry-run
```

## Configuration

Create a YAML specification file with your desired infrastructure:

```yaml
instances:
  - name: "web-server"
    instance_type: "t3.micro"
    ami_id: "ami-0c55b159cbfafe1d0"
    key_name: "my-key"
    security_groups: ["sg-12345"]
    volumes:
      - size: 20
        type: "gp3"
        device: "/dev/sdf"
```

## AWS Credentials

Ensure AWS credentials are configured via:
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- AWS CLI (`aws configure`)
- IAM roles (for EC2 instances)

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

### Command Line Options

- `action`: Required. Either "create" or "delete"
- `--spec, -s`: Required. Path to the YAML specification file
- `--region, -r`: Optional. AWS region (default: us-east-1)
- `--dry-run`: Optional. Show what would be done without executing

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



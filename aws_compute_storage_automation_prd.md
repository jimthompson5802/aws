# Product Requirements Document (PRD)
## Title
AWS Compute and Storage Automation Script

## Objective
Develop a Python script to automate the provisioning of AWS EC2 instances and associated storage volumes based on a predefined specification.

## Background
Manual setup of compute and storage resources in AWS is time-consuming and error-prone. Automating this process will improve efficiency, consistency, and scalability.

## Requirements

### Functional Requirements
1. **Input Specification** ✅ IMPLEMENTED
   - The script must accept a predefined specification in **YAML** format describing:
     - One or more EC2 instances: type, AMI, key pair, security groups, subnet, tags, etc.
     - Instance market type: support both **on-demand and spot instances**.
     - Storage volumes: size, type, device mapping, IOPS, encrypted, etc.
     - **User data script**: optional bash script path or inline script content for instance customization.
     - **Idle Shutdown Policy**: optional configuration to define a CloudWatch alarm that stops the EC2 instance if it is idle (e.g., low CPU utilization) for a pre-defined time period.  Do not shutdown the instance when the EC2 instance first starts up and is missing alert data.  Only shutdown the instance if there is sufficient alert data to determine that the instance is idle.
     - **IAM role**: optional IAM role to associate with the EC2 instance(s).

2. **Resource Provisioning** ✅ IMPLEMENTED
   - Create one or more EC2 instance(s) as per the specification.
   - Attach EBS volumes as specified.
   - Associate IAM role with the instance(s) if specified.
   - Tag resources appropriately.
   - **Execute user data script on instance startup** (if specified).
   - **Configure CloudWatch Alarm for Idle Shutdown**: If specified in the YAML, create a CloudWatch alarm that stops the EC2 instance if it is idle (e.g., CPU utilization below a threshold) for a specified duration.
   - **Output Connection Information**: Print the name and public IP address of the instance(s) after provisioning. ✅ IMPLEMENTED

3. **Instance Customization** ✅ IMPLEMENTED
   - Support for specifying a bash script that runs on EC2 instance startup via user data.
   - The bash script should be capable of:
     - **Cloning git repositories**
     - **Creating Python virtual environments**
     - **Installing Python packages via pip**
     - **Installing system packages**
     - **Configuring applications and services**
     - **Setting up environment variables**
   - Support both inline script content and script file paths in the YAML specification.

4. **Idempotency** ✅ IMPLEMENTED
   - Running the script multiple times with the same specification should not create duplicate resources.

5. **Error Handling** ✅ IMPLEMENTED
   - Provide clear error messages for failed operations.
   - Roll back resources if provisioning fails partway.

6. **Logging** ✅ IMPLEMENTED
   - Log all actions and outcomes for auditability.
   - **Log user data script execution status and output**.

7. **Resource Deletion** ✅ IMPLEMENTED
   - The script should support deletion/teardown of resources as specified.
   - **Remove associated CloudWatch alarms when deleting EC2 instances.**

8. **User Data Monitoring** ✅ NEW FEATURE ADDED
   - Monitor and retrieve user data script execution logs from instances.
   - Command: `python script.py monitor --spec specification.yaml`

### Non-Functional Requirements
- Use boto3 (AWS SDK for Python).
- Script should be runnable from the command line.
- Support for at least one AWS region, defaulting to **us-east** (configurable).
- Documentation for usage and input specification.
- **AWS credentials must be obtained from either environment variables or an AWS profile specified by the user.**
- If a profile is specified (e.g., via a `--profile` command-line argument or in the YAML spec), use that profile; otherwise, default to environment variables.

## Out of Scope
- Configuration of software inside the EC2 instance beyond what's specified in the user data script.
- Management of resources outside EC2 and EBS (e.g., RDS, S3).

## Deliverables ✅ ALL COMPLETED
- Python script(s) ✅
- Example YAML input specification file ✅
- **Example bash scripts for common customization scenarios** ✅
- Documentation (README) ✅

### New Deliverables Added
- **User data script examples in `/examples/` directory**:
  - `python_web_server.sh` - Complete Python Flask web server setup
  - `data_science_setup.sh` - Jupyter Lab and data science environment
  - `docker_deployment.sh` - Docker containerized application deployment
  - `database_setup.sh` - MySQL database server with backup automation
  - `dev_environment.sh` - Complete development environment with VS Code server
- **User data monitoring functionality** - Monitor script execution status
- **Enhanced YAML specification** with user data examples
- **CloudWatch idle shutdown alarm support**: Example YAML and documentation for configuring idle shutdown alarms
- **Connection information output functionality**: Enhanced output display of instance names, IDs, public IP addresses, and SSH commands ✅

## Open Questions
- None (all clarified).

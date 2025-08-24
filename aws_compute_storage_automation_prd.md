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

2. **Resource Provisioning** ✅ IMPLEMENTED
   - Create one or more EC2 instance(s) as per the specification.
   - Attach EBS volumes as specified.
   - Tag resources appropriately.
   - **Execute user data script on instance startup** (if specified).

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

## Open Questions
- None (all clarified).

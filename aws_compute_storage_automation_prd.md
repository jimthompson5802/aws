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
     - Storage volumes: size, type, device mapping, IOPS, encrypted, **mount point**, etc. ✅ **NEW: Mount Point Specification**
       - **Volume Creation Methods**: Support two methods for specifying storage volumes:
         - **Method 1 (Current)**: Create new volumes by specifying size, type, IOPS, encryption
         - **Method 2 (NEW)**: Restore from existing EBS snapshots by specifying snapshot ID ✅ **NEW: Snapshot Restoration**
     - **User data script**: optional bash script path or inline script content for instance customization.
     - **Idle Shutdown Policy**: optional configuration to define a CloudWatch alarm that stops the EC2 instance if it is idle (e.g., low CPU utilization) for a pre-defined time period.  Do not shutdown the instance when the EC2 instance first starts up and is missing alert data.  Only shutdown the instance if there is sufficient alert data to determine that the instance is idle.
     - **IAM role**: optional IAM role to associate with the EC2 instance(s).

2. **Resource Provisioning** ✅ IMPLEMENTED
   - Create one or more EC2 instance(s) as per the specification.
   - Attach EBS volumes as specified.
   - **Automatically format and mount EBS volumes** to specified mount points ✅ **NEW FEATURE**
   - **Restore EBS volumes from snapshots**: When snapshot ID is specified, restore the snapshot to a new EBS volume, attach to EC2 instance, and mount at specified mount point ✅ **NEW: Snapshot Restoration**
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
   - **Snapshot restoration idempotency**: Restoring the same snapshot multiple times should not create duplicate volumes if the target device/mount point already exists.

5. **Error Handling** ✅ IMPLEMENTED
   - Provide clear error messages for failed operations.
   - Roll back resources if provisioning fails partway.
   - **Enhanced snapshot error handling** ✅ **NEW FEATURE**:
     - Invalid or non-existent snapshot IDs
     - Snapshot restoration failures
     - Cross-region snapshot access issues
     - Snapshot creation from volumes not owned by the account
     - Snapshot state validation (completed snapshots only)

6. **Logging** ✅ IMPLEMENTED
   - Log all actions and outcomes for auditability.
   - **Log user data script execution status and output**.

7. **Resource Deletion** ✅ IMPLEMENTED
   - The script should support deletion/teardown of resources as specified.
   - **Remove associated CloudWatch alarms when deleting EC2 instances.**

8. **User Data Monitoring** ✅ NEW FEATURE ADDED
   - Monitor and retrieve user data script execution logs from instances.
   - Command: `python script.py monitor --spec specification.yaml`

9. **Resource Listing Commands**  ✅ **IMPLEMENTED**
   - The script must provide commands to list and inspect AWS resources:
     - **List attached volumes for an EC2 instance by name**:  
       - Command: `python script.py list-attached-volumes --instance-name <name> [--profile <profile>]`
       - Output: List of EBS volumes attached to the running EC2 instance with the specified name, including device mapping and volume details.
     - **List all EBS volumes and their status**:  
       - Command: `python script.py list-volumes [--profile <profile>]`
       - Output: Table of all EBS volumes, their status (e.g., available, in-use), and if in-use, the name of the EC2 instance they are attached to (as specified by the user in the YAML spec or instance tags).
     - **List all EBS snapshots**:  
       - Command: `python script.py list-snapshots [--profile <profile>]`
       - Output: List of all EBS snapshots, including snapshot ID, description, creation time, and associated volume ID.
     - **Create EBS snapshot from volume** ✅ **NEW: Snapshot Creation**:  
       - Command: `python script.py create-snapshot --volume-id <volume-id> [--description <description>] [--profile <profile>]`
       - Output: Snapshot creation details including snapshot ID, status, and estimated completion time.

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
- **Storage Mount Point Specification** ✅ **NEW FEATURE ADDED**:
  - Automatic volume formatting and mounting to specified directories
  - Support for multiple filesystem types (ext4, xfs, btrfs)
  - Persistent mounting via `/etc/fstab` configuration
  - Mount point validation and verification
  - Example YAML: `example_with_mount_points.yaml`
  - Backward compatibility with existing volume specifications
- **Resource listing commands**:
  - List attached volumes for a given EC2 instance by name
  - List all EBS volumes and their status, including attached instance name
  - List all EBS snapshots
  - Example usage in documentation
- **Snapshot Management Functionality** ✅ **NEW FEATURE ADDED**:
  - Snapshot restoration support in volume specifications
  - Create snapshots from existing EBS volumes
  - Automatic volume creation from snapshots with mounting
  - Enhanced YAML specification for snapshot-based workflows
  - Example YAML: `example_with_snapshots.yaml`
  - Backward compatibility with existing volume specifications

## YAML Specification Format Updates

### Volume Specification Methods

The enhanced YAML specification supports two methods for defining storage volumes:

#### Method 1: Create New Volume (Existing)
```yaml
volumes:
  - size: 100                    # Required: Volume size in GB
    type: "gp3"                  # Required: Volume type (gp2, gp3, io1, io2, st1, sc1)
    device: "/dev/sdf"           # Required: Device identifier
    mount_point: "/data"         # Optional: Auto-mount location
    filesystem: "ext4"           # Optional: Filesystem type (ext4, xfs, btrfs)
    mount_options: "defaults"    # Optional: Mount options
    iops: 3000                   # Optional: IOPS (for gp3, io1, io2)
    encrypted: true              # Optional: Enable encryption
```

#### Method 2: Restore from Snapshot (NEW)
```yaml
volumes:
  - snapshot_id: "snap-1234567890abcdef0"  # Required: EBS snapshot ID to restore
    device: "/dev/sdg"                     # Required: Device identifier  
    mount_point: "/restored-data"          # Optional: Auto-mount location
    mount_options: "defaults,noatime"      # Optional: Mount options
    # Note: size, type, encryption, and filesystem inherited from snapshot
```

#### Hybrid Example
```yaml
instances:
  - name: "hybrid-server"
    instance_type: "t3.medium"
    ami_id: "ami-0c02fb55956c7d316"
    volumes:
      # New volume for application data
      - size: 50
        type: "gp3"
        device: "/dev/sdf"
        mount_point: "/app-data"
        encrypted: true
      
      # Restored volume from backup snapshot
      - snapshot_id: "snap-backup-database"
        device: "/dev/sdg"
        mount_point: "/var/lib/mysql"
        mount_options: "defaults,noatime"
      
      # Another new volume for logs
      - size: 20
        type: "gp3"  
        device: "/dev/sdh"
        mount_point: "/var/log"
```

### Snapshot Workflow Examples

#### Backup Workflow
```bash
# 1. Create snapshot from existing volume
python script.py create-snapshot --volume-id vol-1234567890abcdef0 --description "Daily backup of production database"

# 2. List snapshots to verify creation
python script.py list-snapshots

# 3. Use snapshot in new instance specification
# (Reference snapshot ID in YAML volume specification)
```

#### Disaster Recovery Workflow
```bash
# 1. Provision new instance from production snapshot
python script.py provision --spec disaster_recovery_spec.yaml

# disaster_recovery_spec.yaml contains:
# volumes:
#   - snapshot_id: "snap-production-backup"
#     device: "/dev/sdf"
#     mount_point: "/var/lib/mysql"
```

## Open Questions
- None (all clarified).

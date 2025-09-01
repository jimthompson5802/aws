#!/usr/bin/env python3
"""
AWS Compute and Storage Automation Script

This script automates the provisioning of AWS EC2 instances and associated
storage volumes based on a YAML specification.

Requirements:
- boto3
- PyYAML
- AWS credentials configured via environment variables
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import yaml
import boto3
from botocore.exceptions import ClientError


class AWSResourceManager:
    """Manages AWS EC2 instances and EBS volumes with idempotency and rollback support."""

    def __init__(self, region: str = "us-east-1", profile: Optional[str] = None):
        """Initialize the AWS resource manager.

        Args:
            region: AWS region to operate in
            profile: AWS profile name to use for authentication
        """
        self.region = region
        self.profile = profile

        # Create boto3 session with or without profile
        if profile:
            self.session = boto3.Session(profile_name=profile)
            self.logger = logging.getLogger(__name__)
            self.logger.info(f"Using AWS profile: {profile}")
        else:
            self.session = boto3.Session()
            self.logger = logging.getLogger(__name__)
            self.logger.info(
                "Using default AWS credentials (environment variables or default profile)"
            )

        self.ec2_client = self.session.client("ec2", region_name=region)
        self.ec2_resource = self.session.resource("ec2", region_name=region)
        self.cloudwatch_client = self.session.client("cloudwatch", region_name=region)
        self.created_resources = {"instances": [], "volumes": [], "alarms": []}

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("aws_automation.log"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        # Logger was already initialized above, so we don't need to reinitialize it

    def load_specification(self, spec_file: str) -> Dict[str, Any]:
        """Load and validate YAML specification file.

        Args:
            spec_file: Path to the YAML specification file

        Returns:
            Parsed specification dictionary

        Raises:
            FileNotFoundError: If specification file doesn't exist
            yaml.YAMLError: If YAML is invalid
            ValueError: If specification is invalid
        """
        try:
            with open(spec_file, "r") as f:
                spec = yaml.safe_load(f)
            self.logger.info(f"Loaded specification from {spec_file}")
            self._validate_specification(spec)
            return spec
        except FileNotFoundError:
            self.logger.error(f"Specification file not found: {spec_file}")
            raise
        except yaml.YAMLError as e:
            self.logger.error(f"Invalid YAML in specification file: {e}")
            raise

    def _validate_specification(self, spec: Dict[str, Any]) -> None:
        """Validate the specification structure.

        Args:
            spec: Specification dictionary to validate

        Raises:
            ValueError: If specification is invalid
        """
        required_fields = ["instances"]
        for field in required_fields:
            if field not in spec:
                raise ValueError(f"Missing required field in specification: {field}")

        # Validate optional profile field
        if "profile" in spec:
            if not isinstance(spec["profile"], str):
                raise ValueError("Profile field must be a string")

        for i, instance in enumerate(spec["instances"]):
            required_instance_fields = ["name", "instance_type", "ami_id"]
            for field in required_instance_fields:
                if field not in instance:
                    raise ValueError(
                        f"Missing required field '{field}' in instance {i}"
                    )

            # Validate user data configuration
            if "user_data" in instance:
                user_data = instance["user_data"]
                if not isinstance(user_data, dict):
                    raise ValueError(f"user_data must be an object in instance {i}")

                if "script_path" in user_data and "inline_script" in user_data:
                    raise ValueError(
                        f"Cannot specify both script_path and inline_script in instance {i}"
                    )

                if "script_path" not in user_data and "inline_script" not in user_data:
                    raise ValueError(
                        f"user_data must contain either script_path or inline_script in instance {i}"
                    )

            # Validate idle shutdown configuration
            if "idle_shutdown" in instance:
                idle_config = instance["idle_shutdown"]
                if not isinstance(idle_config, dict):
                    raise ValueError(f"idle_shutdown must be an object in instance {i}")

                required_idle_fields = ["cpu_threshold", "evaluation_minutes"]
                for field in required_idle_fields:
                    if field not in idle_config:
                        raise ValueError(
                            f"Missing required field '{field}' in idle_shutdown config for instance {i}"
                        )

                # Validate threshold is between 0 and 100
                threshold = idle_config["cpu_threshold"]
                if (
                    not isinstance(threshold, (int, float))
                    or threshold < 0
                    or threshold > 100
                ):
                    raise ValueError(
                        f"cpu_threshold must be a number between 0 and 100 in instance {i}"
                    )

                # Validate evaluation_minutes is positive
                eval_mins = idle_config["evaluation_minutes"]
                if not isinstance(eval_mins, int) or eval_mins <= 0:
                    raise ValueError(
                        f"evaluation_minutes must be a positive integer in instance {i}"
                    )

                # Validate action if specified
                if "action" in idle_config:
                    valid_actions = ["stop", "terminate"]
                    if idle_config["action"] not in valid_actions:
                        raise ValueError(
                            f"idle_shutdown action must be one of {valid_actions} in instance {i}"
                        )

            # Validate IAM role configuration
            if "iam_role" in instance:
                iam_role = instance["iam_role"]
                if not isinstance(iam_role, str) or not iam_role.strip():
                    raise ValueError(
                        f"iam_role must be a non-empty string in instance {i}"
                    )

            # Validate volume specifications including mount points
            if "volumes" in instance:
                for j, volume in enumerate(instance["volumes"]):
                    self._validate_volume_spec(volume, i, j)

        self.logger.info("Specification validation passed")

    def _validate_volume_spec(
        self, volume_spec: Dict[str, Any], instance_idx: int, volume_idx: int
    ) -> None:
        """Validate volume specification including mount points.

        Args:
            volume_spec: Volume specification to validate
            instance_idx: Instance index for error reporting
            volume_idx: Volume index for error reporting
        """
        # Check required fields
        required_fields = ["size"]
        for field in required_fields:
            if field not in volume_spec:
                raise ValueError(
                    f"Volume specification missing required field '{field}' "
                    f"in instance {instance_idx}, volume {volume_idx}"
                )

        # Validate size
        size = volume_spec["size"]
        if not isinstance(size, int) or size <= 0:
            raise ValueError(
                f"Volume size must be a positive integer in instance {instance_idx}, volume {volume_idx}"
            )

        # Validate volume type if specified
        if "type" in volume_spec:
            valid_types = ["gp2", "gp3", "io1", "io2", "st1", "sc1"]
            if volume_spec["type"] not in valid_types:
                raise ValueError(
                    f"Invalid volume type '{volume_spec['type']}' in instance {instance_idx}, "
                    f"volume {volume_idx}. Must be one of: {valid_types}"
                )

        # Validate mount point if specified
        if "mount_point" in volume_spec:
            mount_point = volume_spec["mount_point"]
            if not isinstance(mount_point, str) or not mount_point.strip():
                raise ValueError(
                    f"Mount point must be a non-empty string in instance {instance_idx}, volume {volume_idx}"
                )

            if not mount_point.startswith("/"):
                raise ValueError(
                    f"Mount point must be an absolute path in instance {instance_idx}, volume {volume_idx}"
                )

            # Warn about potentially dangerous mount points
            dangerous_paths = [
                "/",
                "/boot",
                "/etc",
                "/usr",
                "/bin",
                "/sbin",
                "/lib",
                "/lib64",
            ]
            if mount_point in dangerous_paths:
                raise ValueError(
                    f"Mount point '{mount_point}' is a reserved system directory "
                    f"in instance {instance_idx}, volume {volume_idx}"
                )

        # Validate filesystem type if specified
        if "filesystem" in volume_spec:
            supported_filesystems = ["ext4", "xfs", "btrfs"]
            if volume_spec["filesystem"] not in supported_filesystems:
                raise ValueError(
                    f"Unsupported filesystem '{volume_spec['filesystem']}' in instance {instance_idx}, "
                    f"volume {volume_idx}. Supported: {supported_filesystems}"
                )

        # Validate mount options if specified
        if "mount_options" in volume_spec:
            mount_options = volume_spec["mount_options"]
            if not isinstance(mount_options, str) or not mount_options.strip():
                raise ValueError(
                    f"Mount options must be a non-empty string in instance {instance_idx}, volume {volume_idx}"
                )

        # Validate device name if specified
        if "device" in volume_spec:
            device = volume_spec["device"]
            if not isinstance(device, str) or not device.startswith("/dev/"):
                raise ValueError(
                    f"Device must be a valid device path (e.g., /dev/sdf) "
                    f"in instance {instance_idx}, volume {volume_idx}"
                )

    def _get_existing_resources(self, spec: Dict[str, Any]) -> Dict[str, List]:
        """Check for existing resources to ensure idempotency.

        Args:
            spec: Resource specification

        Returns:
            Dictionary of existing resources
        """
        existing = {"instances": [], "volumes": []}

        # Check for existing instances by name tag
        for instance_spec in spec["instances"]:
            instance_name = instance_spec["name"]
            try:
                response = self.ec2_client.describe_instances(
                    Filters=[
                        {"Name": "tag:Name", "Values": [instance_name]},
                        {
                            "Name": "instance-state-name",
                            "Values": ["running", "pending", "stopped"],
                        },
                    ]
                )

                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        existing["instances"].append(
                            {
                                "id": instance["InstanceId"],
                                "name": instance_name,
                                "state": instance["State"]["Name"],
                            }
                        )
                        self.logger.info(
                            f"Found existing instance: {instance['InstanceId']} ({instance_name})"
                        )

            except ClientError as e:
                self.logger.warning(f"Error checking for existing instances: {e}")

        return existing

    def _generate_volume_mount_script(self, instance_spec: Dict[str, Any]) -> str:
        """Generate script commands to format and mount EBS volumes.

        Args:
            instance_spec: Instance specification containing volume definitions

        Returns:
            Script content for mounting volumes
        """
        mount_commands = []

        if "volumes" not in instance_spec:
            return ""

        volumes_with_mounts = [
            v for v in instance_spec["volumes"] if "mount_point" in v
        ]
        if not volumes_with_mounts:
            return ""

        mount_commands.extend(
            [
                "# === AUTOMATIC VOLUME MOUNTING ===",
                "echo 'Starting volume mounting process...'",
                "",
                "# Function to wait for device",
                "wait_for_device() {",
                "    local device=$1",
                "    local timeout=300  # 5 minutes",
                "    local count=0",
                '    echo "Waiting for device $device to be available..."',
                '    while [ ! -e "$device" ] && [ $count -lt $timeout ]; do',
                "        sleep 1",
                "        count=$((count + 1))",
                "    done",
                '    if [ ! -e "$device" ]; then',
                '        echo "ERROR: Device $device not available after ${timeout}s"',
                "        return 1",
                "    fi",
                '    echo "Device $device is available"',
                "    return 0",
                "}",
                "",
                "# Function to check if device is already formatted",
                "is_formatted() {",
                "    local device=$1",
                '    blkid "$device" >/dev/null 2>&1',
                "}",
                "",
            ]
        )

        for volume in volumes_with_mounts:
            device = volume.get("device", "/dev/sdf")
            mount_point = volume["mount_point"]
            filesystem = volume.get("filesystem", "ext4")
            mount_options = volume.get("mount_options", "defaults")

            mount_commands.extend(
                [
                    f"# Mount {device} to {mount_point}",
                    f"echo 'Processing volume: {device} -> {mount_point}'",
                    "",
                    "# Wait for device to be available",
                    f"if ! wait_for_device '{device}'; then",
                    f"    echo 'ERROR: Failed to mount {device} - device not available'",
                    "    exit 1",
                    "fi",
                    "",
                    "# Create mount point directory",
                    f"mkdir -p '{mount_point}'",
                    "",
                    "# Format the volume if not already formatted",
                    f"if ! is_formatted '{device}'; then",
                    f"    echo 'Formatting {device} with {filesystem} filesystem...'",
                    f"    mkfs.{filesystem} '{device}'",
                    "    if [ $? -ne 0 ]; then",
                    f"        echo 'ERROR: Failed to format {device}'",
                    "        exit 1",
                    "    fi",
                    "else",
                    f"    echo 'Device {device} is already formatted'",
                    "fi",
                    "",
                    "# Mount the volume",
                    f"echo 'Mounting {device} to {mount_point}...'",
                    f"mount -o '{mount_options}' '{device}' '{mount_point}'",
                    "if [ $? -ne 0 ]; then",
                    f"    echo 'ERROR: Failed to mount {device} to {mount_point}'",
                    "    exit 1",
                    "fi",
                    "",
                    "# Add to fstab for persistence",
                    f"if ! grep -q '^{device}' /etc/fstab; then",
                    f"    echo '{device} {mount_point} {filesystem} {mount_options} 0 2' >> /etc/fstab",
                    f"    echo 'Added {device} to /etc/fstab'",
                    "else",
                    f"    echo 'Entry for {device} already exists in /etc/fstab'",
                    "fi",
                    "",
                    "# Set permissions (make accessible to ec2-user)",
                    f"chown ec2-user:ec2-user '{mount_point}'",
                    f"chmod 755 '{mount_point}'",
                    "",
                    f"echo 'Successfully mounted {device} to {mount_point}'",
                    "",
                ]
            )

        mount_commands.extend(
            [
                "echo 'Volume mounting process completed'",
                "echo 'Current mounts:'",
                "df -h",
                "",
            ]
        )

        return "\n".join(mount_commands)

    def _prepare_user_data(self, instance_spec: Dict[str, Any]) -> str:
        """Prepare user data script with volume mounting and user scripts.

        Args:
            instance_spec: Instance specification containing user data and volumes

        Returns:
            User data script content (base64 will be handled by boto3)

        Raises:
            FileNotFoundError: If script file doesn't exist
            Exception: If script preparation fails
        """
        user_data_parts = [
            "#!/bin/bash",
            "# AWS Automation Script - User Data Execution",
            f"# Instance: {instance_spec['name']}",
            f"# Generated: {datetime.now().isoformat()}",
            "",
            "set -e  # Exit on any error",
            "",
            "# Set up logging",
            'LOG_FILE="/var/log/user-data-execution.log"',
            'exec > >(tee -a "$LOG_FILE")',
            "exec 2>&1",
            "",
            'echo "===== User Data Script Execution Started ====="',
            'echo "Timestamp: $(date)"',
            f"echo \"Instance Name: {instance_spec['name']}\"",
            'echo "=============================================="',
            "",
        ]

        # 1. Add volume mounting commands first (if volumes with mount points exist)
        mount_script = self._generate_volume_mount_script(instance_spec)
        if mount_script:
            user_data_parts.extend(
                [mount_script, 'echo "Volume mounting completed successfully"', ""]
            )

        # 2. Add user's custom script
        user_data_config = instance_spec.get("user_data", {})
        if user_data_config:
            user_data_parts.extend(
                [
                    "# === USER CUSTOM SCRIPT ===",
                    'echo "Starting user custom script..."',
                    "",
                ]
            )

            try:
                if "script_path" in user_data_config:
                    # Load script from file
                    script_path = user_data_config["script_path"]
                    with open(script_path, "r") as f:
                        script_content = f.read()
                    user_data_parts.append(script_content)
                    self.logger.info(f"Loaded user data script from {script_path}")
                elif "inline_script" in user_data_config:
                    # Use inline script content
                    script_content = user_data_config["inline_script"]
                    user_data_parts.append(script_content)
                    self.logger.info("Using inline user data script")
            except FileNotFoundError:
                self.logger.error(
                    f"User data script file not found: {user_data_config.get('script_path')}"
                )
                raise
            except Exception as e:
                self.logger.error(f"Failed to load user data script: {e}")
                raise

        # 3. Add verification commands for volumes with mount points
        volumes_with_mounts = [
            v for v in instance_spec.get("volumes", []) if "mount_point" in v
        ]
        if volumes_with_mounts:
            user_data_parts.extend(
                [
                    "",
                    "# === MOUNT VERIFICATION ===",
                    'echo "Verifying mounts..."',
                    "df -h",
                ]
            )

            # Check each mounted volume
            for volume in volumes_with_mounts:
                mount_point = volume["mount_point"]
                user_data_parts.extend(
                    [
                        f"if mountpoint -q '{mount_point}'; then",
                        f'    echo "✓ {mount_point} is properly mounted"',
                        "else",
                        f'    echo "✗ ERROR: {mount_point} is not mounted"',
                        "    exit 1",
                        "fi",
                    ]
                )

            user_data_parts.extend(
                ['echo "All mount points verified successfully"', ""]
            )

        # 4. Final completion message
        user_data_parts.extend(
            [
                'echo "=============================================="',
                'echo "User Data Script Execution Completed Successfully"',
                'echo "Timestamp: $(date)"',
                'echo "=============================================="',
            ]
        )

        final_script = "\n".join(user_data_parts)

        # Log volume mounting info if applicable
        if volumes_with_mounts:
            mount_info = [
                f"{v.get('device', '/dev/sdf')} -> {v['mount_point']}"
                for v in volumes_with_mounts
            ]
            self.logger.info(
                f"Added volume mounting to user data: {', '.join(mount_info)}"
            )

        return final_script

    def _create_ec2_instance(self, instance_spec: Dict[str, Any]) -> str:
        """Create a single EC2 instance.

        Args:
            instance_spec: Instance specification

        Returns:
            Instance ID of created instance

        Raises:
            ClientError: If instance creation fails
        """
        instance_params = {
            "ImageId": instance_spec["ami_id"],
            "InstanceType": instance_spec["instance_type"],
            "MinCount": 1,
            "MaxCount": 1,
            "TagSpecifications": [
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": instance_spec["name"]},
                        {"Key": "CreatedBy", "Value": "aws-automation-script"},
                        {"Key": "CreatedAt", "Value": datetime.now().isoformat()},
                    ],
                }
            ],
        }

        # Add optional parameters
        if "key_name" in instance_spec:
            instance_params["KeyName"] = instance_spec["key_name"]

        if "security_groups" in instance_spec:
            instance_params["SecurityGroupIds"] = instance_spec["security_groups"]

        if "subnet_id" in instance_spec:
            instance_params["SubnetId"] = instance_spec["subnet_id"]

        # Handle spot instances
        market_type = instance_spec.get("market_type", "on-demand")
        if market_type == "spot":
            instance_params["InstanceMarketOptions"] = {
                "MarketType": "spot",
                "SpotOptions": {"SpotInstanceType": "one-time"},
            }
            if "spot_price" in instance_spec:
                instance_params["InstanceMarketOptions"]["SpotOptions"]["MaxPrice"] = (
                    str(instance_spec["spot_price"])
                )

        # Add custom tags
        if "tags" in instance_spec:
            for tag in instance_spec["tags"]:
                instance_params["TagSpecifications"][0]["Tags"].append(tag)

        # Add user data script if specified
        user_data_script = self._prepare_user_data(instance_spec)
        if user_data_script:
            instance_params["UserData"] = user_data_script
            self.logger.info(
                f"Added user data script to instance {instance_spec['name']}"
            )

        # Add IAM instance profile if specified
        if "iam_role" in instance_spec:
            iam_role = instance_spec["iam_role"]
            instance_params["IamInstanceProfile"] = {"Name": iam_role}
            self.logger.info(
                f"Added IAM instance profile {iam_role} to instance {instance_spec['name']}"
            )

        try:
            response = self.ec2_client.run_instances(**instance_params)
            instance_id = response["Instances"][0]["InstanceId"]

            self.logger.info(
                f"Created EC2 instance: {instance_id} ({instance_spec['name']})"
            )
            self.created_resources["instances"].append(instance_id)

            # Wait for instance to be running
            self.logger.info(f"Waiting for instance {instance_id} to be running...")
            waiter = self.ec2_client.get_waiter("instance_running")
            waiter.wait(
                InstanceIds=[instance_id], WaiterConfig={"Delay": 5, "MaxAttempts": 60}
            )

            return instance_id

        except ClientError as e:
            self.logger.error(f"Failed to create instance {instance_spec['name']}: {e}")
            raise

    def _create_and_attach_volumes(
        self, instance_id: str, instance_spec: Dict[str, Any]
    ) -> List[str]:
        """Create and attach EBS volumes to an instance.

        Args:
            instance_id: ID of the instance to attach volumes to
            instance_spec: Instance specification containing volume definitions

        Returns:
            List of created volume IDs
        """
        created_volume_ids = []

        if "volumes" not in instance_spec:
            return created_volume_ids

        # Get instance AZ
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            availability_zone = response["Reservations"][0]["Instances"][0][
                "Placement"
            ]["AvailabilityZone"]
        except ClientError as e:
            self.logger.error(f"Failed to get instance AZ: {e}")
            raise

        for volume_spec in instance_spec["volumes"]:
            try:
                volume_params = {
                    "Size": volume_spec["size"],
                    "VolumeType": volume_spec.get("type", "gp3"),
                    "AvailabilityZone": availability_zone,
                    "TagSpecifications": [
                        {
                            "ResourceType": "volume",
                            "Tags": [
                                {
                                    "Key": "Name",
                                    "Value": f"{instance_spec['name']}-{volume_spec.get('device', 'additional')}",
                                },
                                {"Key": "CreatedBy", "Value": "aws-automation-script"},
                                {
                                    "Key": "CreatedAt",
                                    "Value": datetime.now().isoformat(),
                                },
                            ],
                        }
                    ],
                }

                # Add optional volume parameters
                if "iops" in volume_spec and volume_spec.get("type") in [
                    "gp3",
                    "io1",
                    "io2",
                ]:
                    volume_params["Iops"] = volume_spec["iops"]

                if volume_spec.get("encrypted", False):
                    volume_params["Encrypted"] = True

                # Create volume
                response = self.ec2_client.create_volume(**volume_params)
                volume_id = response["VolumeId"]

                self.logger.info(f"Created EBS volume: {volume_id}")
                self.created_resources["volumes"].append(volume_id)
                created_volume_ids.append(volume_id)

                # Wait for volume to be available
                waiter = self.ec2_client.get_waiter("volume_available")
                waiter.wait(
                    VolumeIds=[volume_id], WaiterConfig={"Delay": 5, "MaxAttempts": 60}
                )

                # Attach volume
                device = volume_spec.get("device", "/dev/sdf")
                self.ec2_client.attach_volume(
                    VolumeId=volume_id, InstanceId=instance_id, Device=device
                )

                self.logger.info(
                    f"Attached volume {volume_id} to instance {instance_id} at {device}"
                )

            except ClientError as e:
                self.logger.error(f"Failed to create/attach volume: {e}")
                raise

        return created_volume_ids

    def _create_idle_shutdown_alarm(
        self, instance_id: str, instance_spec: Dict[str, Any]
    ) -> str:
        """Create CloudWatch alarm for idle shutdown detection.

        Args:
            instance_id: ID of the instance to monitor
            instance_spec: Instance specification containing idle_shutdown config

        Returns:
            CloudWatch alarm name

        Raises:
            ClientError: If alarm creation fails
        """
        if "idle_shutdown" not in instance_spec:
            return None

        idle_config = instance_spec["idle_shutdown"]
        instance_name = instance_spec["name"]

        # Default values
        cpu_threshold = idle_config["cpu_threshold"]
        evaluation_minutes = idle_config["evaluation_minutes"]
        action = idle_config.get("action", "stop")  # Default to stop

        alarm_name = f"idle-shutdown-{instance_name}-{instance_id}"
        alarm_description = (
            f"Idle shutdown alarm for {instance_name} - {action} "
            f"instance when CPU < {cpu_threshold}% for {evaluation_minutes} minutes"
        )

        try:
            # Check if alarm already exists (for idempotency)
            try:
                existing_alarms = self.cloudwatch_client.describe_alarms(
                    AlarmNames=[alarm_name]
                )
                if existing_alarms.get("MetricAlarms"):
                    self.logger.info(
                        f"CloudWatch alarm {alarm_name} already exists, skipping creation"
                    )
                    return alarm_name
            except ClientError:
                # Alarm doesn't exist, proceed with creation
                pass

            # Create the alarm
            self.cloudwatch_client.put_metric_alarm(
                AlarmName=alarm_name,
                AlarmDescription=alarm_description,
                ActionsEnabled=True,
                AlarmActions=[f"arn:aws:automate:{self.region}:ec2:{action}"],
                MetricName="CPUUtilization",
                Namespace="AWS/EC2",
                Statistic="Average",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                Period=300,  # 5 minutes
                EvaluationPeriods=evaluation_minutes
                // 5,  # Convert minutes to 5-minute periods
                Threshold=cpu_threshold,
                ComparisonOperator="LessThanThreshold",
                TreatMissingData="notBreaching",  # Don't shutdown when missing data (e.g., during startup)
            )

            self.logger.info(
                f"Created CloudWatch alarm: {alarm_name} for instance {instance_id}"
            )
            self.created_resources["alarms"].append(alarm_name)
            return alarm_name

        except ClientError as e:
            self.logger.error(
                f"Failed to create CloudWatch alarm for instance {instance_id}: {e}"
            )
            raise

    def provision_resources(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Provision all resources according to specification.

        Args:
            spec: Resource specification

        Returns:
            Dictionary of created resource IDs and connection information

        Raises:
            Exception: If provisioning fails
        """
        self.logger.info("Starting resource provisioning...")

        # Check for existing resources (idempotency)
        existing = self._get_existing_resources(spec)
        if existing["instances"]:
            self.logger.warning(
                "Found existing instances. Skipping creation to maintain idempotency."
            )
            # Get connection info for existing instances
            connection_info = self.get_instance_connection_info(existing["instances"])
            return {
                "instances": existing["instances"],
                "volumes": existing["volumes"],
                "alarms": existing["alarms"],
                "connection_info": connection_info,
            }

        provisioned = {"instances": [], "volumes": [], "alarms": []}

        try:
            for instance_spec in spec["instances"]:
                # Create instance
                instance_id = self._create_ec2_instance(instance_spec)
                provisioned["instances"].append(instance_id)

                # Create and attach volumes
                volume_ids = self._create_and_attach_volumes(instance_id, instance_spec)
                provisioned["volumes"].extend(volume_ids)

                # Create CloudWatch idle shutdown alarm if configured
                alarm_name = self._create_idle_shutdown_alarm(
                    instance_id, instance_spec
                )
                if alarm_name:
                    provisioned["alarms"].append(alarm_name)

            # Get connection information for all provisioned instances
            connection_info = self.get_instance_connection_info(
                provisioned["instances"]
            )
            provisioned["connection_info"] = connection_info

            self.logger.info("Resource provisioning completed successfully")
            return provisioned

        except Exception as e:
            self.logger.error(f"Provisioning failed: {e}")
            self.logger.info("Starting rollback...")
            self.rollback_resources()
            raise

    def rollback_resources(self) -> None:
        """Roll back all created resources in case of failure."""
        self.logger.info("Rolling back created resources...")

        # Delete CloudWatch alarms
        for alarm_name in self.created_resources["alarms"]:
            try:
                self.cloudwatch_client.delete_alarms(AlarmNames=[alarm_name])
                self.logger.info(f"Deleted CloudWatch alarm: {alarm_name}")
            except ClientError as e:
                # Don't fail rollback if alarm deletion fails
                self.logger.warning(
                    f"Failed to delete CloudWatch alarm {alarm_name}: {e}"
                )

        # Detach and delete volumes
        for volume_id in self.created_resources["volumes"]:
            try:
                # Get volume info
                response = self.ec2_client.describe_volumes(VolumeIds=[volume_id])
                volume = response["Volumes"][0]

                # Detach if attached
                if volume["State"] == "in-use":
                    for attachment in volume["Attachments"]:
                        self.ec2_client.detach_volume(VolumeId=volume_id)
                        self.logger.info(f"Detached volume {volume_id}")

                        # Wait for detachment
                        waiter = self.ec2_client.get_waiter("volume_available")
                        waiter.wait(
                            VolumeIds=[volume_id],
                            WaiterConfig={"Delay": 5, "MaxAttempts": 60},
                        )

                # Delete volume
                self.ec2_client.delete_volume(VolumeId=volume_id)
                self.logger.info(f"Deleted volume {volume_id}")

            except ClientError as e:
                self.logger.error(f"Failed to rollback volume {volume_id}: {e}")

        # Terminate instances
        if self.created_resources["instances"]:
            try:
                self.ec2_client.terminate_instances(
                    InstanceIds=self.created_resources["instances"]
                )
                self.logger.info(
                    f"Terminated instances: {self.created_resources['instances']}"
                )
            except ClientError as e:
                self.logger.error(f"Failed to terminate instances: {e}")

    def delete_resources(self, spec: Dict[str, Any]) -> None:
        """Delete resources specified in the configuration.

        Args:
            spec: Resource specification
        """
        self.logger.info("Starting resource deletion...")

        instances_to_delete = []
        volumes_to_delete = []
        alarms_to_delete = []

        # Find instances to delete
        for instance_spec in spec["instances"]:
            instance_name = instance_spec["name"]
            try:
                response = self.ec2_client.describe_instances(
                    Filters=[
                        {"Name": "tag:Name", "Values": [instance_name]},
                        {
                            "Name": "instance-state-name",
                            "Values": ["running", "pending", "stopped"],
                        },
                    ]
                )

                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]
                        instances_to_delete.append(instance_id)

                        # Find attached volumes
                        for bdm in instance.get("BlockDeviceMappings", []):
                            if "Ebs" in bdm:
                                volumes_to_delete.append(bdm["Ebs"]["VolumeId"])

                        # Find associated CloudWatch alarms for idle shutdown
                        alarm_name = f"idle-shutdown-{instance_name}-{instance_id}"
                        alarms_to_delete.append(alarm_name)

            except ClientError as e:
                self.logger.error(f"Error finding instances to delete: {e}")

        # Delete CloudWatch alarms first
        if alarms_to_delete:
            try:
                # Check which alarms actually exist before trying to delete them
                existing_alarms = []
                try:
                    response = self.cloudwatch_client.describe_alarms(
                        AlarmNames=alarms_to_delete
                    )
                    existing_alarms = [
                        alarm["AlarmName"] for alarm in response["MetricAlarms"]
                    ]
                except ClientError as e:
                    # If describe_alarms fails, we'll try to delete anyway and handle errors individually
                    self.logger.warning(f"Could not describe alarms: {e}")
                    existing_alarms = alarms_to_delete

                if existing_alarms:
                    self.cloudwatch_client.delete_alarms(AlarmNames=existing_alarms)
                    self.logger.info(f"Deleted CloudWatch alarms: {existing_alarms}")
                else:
                    self.logger.info("No CloudWatch alarms found to delete")

            except ClientError as e:
                # Don't fail the entire operation if alarm deletion fails
                self.logger.warning(f"Failed to delete some CloudWatch alarms: {e}")

        # Terminate instances
        if instances_to_delete:
            try:
                self.ec2_client.terminate_instances(InstanceIds=instances_to_delete)
                self.logger.info(f"Terminated instances: {instances_to_delete}")

                # Wait for termination
                waiter = self.ec2_client.get_waiter("instance_terminated")
                waiter.wait(
                    InstanceIds=instances_to_delete,
                    WaiterConfig={"Delay": 10, "MaxAttempts": 60},
                )

            except ClientError as e:
                self.logger.error(f"Failed to terminate instances: {e}")

        # Delete volumes (they should be automatically deleted when instances are
        # terminated if DeleteOnTermination is True)
        self.logger.info("Resource deletion completed")

    def get_user_data_logs(self, instance_id: str) -> str:
        """Retrieve user data execution logs from an instance.

        Args:
            instance_id: ID of the instance to get logs from

        Returns:
            User data execution logs

        Raises:
            ClientError: If unable to retrieve logs
        """
        try:
            # Get console output which includes user data execution
            response = self.ec2_client.get_console_output(
                InstanceId=instance_id, Latest=True
            )
            console_output = response.get("Output", "")

            self.logger.info(f"Retrieved console output for instance {instance_id}")

            # Extract user data related logs
            if "User Data Script Execution" in console_output:
                lines = console_output.split("\n")
                user_data_logs = []
                capturing = False

                for line in lines:
                    if "User Data Script Execution Started" in line:
                        capturing = True
                    if capturing:
                        user_data_logs.append(line)
                    if "User Data Script Execution Completed" in line:
                        capturing = False
                        break

                return "\n".join(user_data_logs)
            else:
                return "No user data execution logs found in console output."

        except ClientError as e:
            self.logger.error(
                f"Failed to retrieve console output for {instance_id}: {e}"
            )
            raise

    def monitor_user_data_execution(self, spec: Dict[str, Any]) -> Dict[str, str]:
        """Monitor user data script execution for all instances in the specification.

        Args:
            spec: Resource specification

        Returns:
            Dictionary mapping instance names to their user data execution logs
        """
        self.logger.info("Monitoring user data script execution...")

        logs = {}

        for instance_spec in spec["instances"]:
            if "user_data" not in instance_spec:
                continue

            instance_name = instance_spec["name"]

            # Find the instance by name tag
            try:
                response = self.ec2_client.describe_instances(
                    Filters=[
                        {"Name": "tag:Name", "Values": [instance_name]},
                        {"Name": "instance-state-name", "Values": ["running"]},
                    ]
                )

                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]

                        try:
                            user_data_logs = self.get_user_data_logs(instance_id)
                            logs[instance_name] = user_data_logs
                            self.logger.info(
                                f"Retrieved user data logs for {instance_name} ({instance_id})"
                            )
                        except Exception as e:
                            logs[instance_name] = f"Failed to retrieve logs: {e}"
                            self.logger.error(
                                f"Failed to retrieve user data logs for {instance_name}: {e}"
                            )

            except ClientError as e:
                logs[instance_name] = f"Failed to find instance: {e}"
                self.logger.error(f"Failed to find instance {instance_name}: {e}")

        return logs

    def get_cloudwatch_alarms(self, spec: Dict[str, Any]) -> Dict[str, str]:
        """Get CloudWatch alarms for instances in the specification.

        Args:
            spec: Resource specification

        Returns:
            Dictionary mapping instance names to alarm states
        """
        alarm_states = {}

        for instance_spec in spec["instances"]:
            instance_name = instance_spec["name"]

            # Skip instances without idle shutdown configuration
            if "idle_shutdown" not in instance_spec:
                alarm_states[instance_name] = "No idle shutdown configured"
                continue

            try:
                # Find the instance
                response = self.ec2_client.describe_instances(
                    Filters=[
                        {"Name": "tag:Name", "Values": [instance_name]},
                        {
                            "Name": "instance-state-name",
                            "Values": ["running", "pending", "stopped", "stopping"],
                        },
                    ]
                )

                instance_found = False
                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]
                        alarm_name = f"idle-shutdown-{instance_name}-{instance_id}"

                        # Check alarm state
                        try:
                            alarm_response = self.cloudwatch_client.describe_alarms(
                                AlarmNames=[alarm_name]
                            )

                            if alarm_response.get("MetricAlarms"):
                                alarm = alarm_response["MetricAlarms"][0]
                                state = alarm.get("StateValue", "UNKNOWN")
                                reason = alarm.get("StateReason", "")
                                alarm_states[instance_name] = (
                                    f"Alarm: {state} - {reason}"
                                )
                            else:
                                alarm_states[instance_name] = "Alarm not found"

                        except ClientError as e:
                            alarm_states[instance_name] = f"Error checking alarm: {e}"

                        instance_found = True
                        break

                    if instance_found:
                        break

                if not instance_found:
                    alarm_states[instance_name] = "Instance not found"

            except ClientError as e:
                alarm_states[instance_name] = f"Error finding instance: {e}"

        return alarm_states

    def get_instance_connection_info(
        self, instance_ids: List[str]
    ) -> List[Dict[str, str]]:
        """Get connection information for instances.

        Args:
            instance_ids: List of instance IDs to get connection info for

        Returns:
            List of dictionaries containing name and public IP for each instance

        Raises:
            ClientError: If unable to retrieve instance information
        """
        connection_info = []

        if not instance_ids:
            return connection_info

        try:
            response = self.ec2_client.describe_instances(InstanceIds=instance_ids)

            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    instance_id = instance["InstanceId"]
                    instance_name = "Unknown"
                    public_ip = instance.get("PublicIpAddress", "No public IP")

                    # Get instance name from tags
                    for tag in instance.get("Tags", []):
                        if tag["Key"] == "Name":
                            instance_name = tag["Value"]
                            break

                    connection_info.append(
                        {
                            "instance_id": instance_id,
                            "name": instance_name,
                            "public_ip": public_ip,
                            "state": instance["State"]["Name"],
                        }
                    )

            self.logger.info(
                f"Retrieved connection information for {len(connection_info)} instances"
            )
            return connection_info

        except ClientError as e:
            self.logger.error(
                f"Failed to retrieve instance connection information: {e}"
            )
            raise

    def get_connection_info_by_spec(self, spec: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get connection information for instances specified in the YAML spec.

        Args:
            spec: Resource specification

        Returns:
            List of dictionaries containing connection information for each instance

        Raises:
            ClientError: If unable to retrieve instance information
        """
        all_connection_info = []

        for instance_spec in spec["instances"]:
            instance_name = instance_spec["name"]

            try:
                # Find instances by name tag
                response = self.ec2_client.describe_instances(
                    Filters=[
                        {"Name": "tag:Name", "Values": [instance_name]},
                        {
                            "Name": "instance-state-name",
                            "Values": ["running", "pending", "stopped", "stopping"],
                        },
                    ]
                )

                for reservation in response["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_id = instance["InstanceId"]
                        public_ip = instance.get("PublicIpAddress", "No public IP")

                        all_connection_info.append(
                            {
                                "instance_id": instance_id,
                                "name": instance_name,
                                "public_ip": public_ip,
                                "state": instance["State"]["Name"],
                            }
                        )

            except ClientError as e:
                self.logger.error(f"Failed to find instance {instance_name}: {e}")
                # Add entry indicating instance not found
                all_connection_info.append(
                    {
                        "instance_id": "N/A",
                        "name": instance_name,
                        "public_ip": "Instance not found",
                        "state": "unknown",
                    }
                )

        return all_connection_info

    def list_attached_volumes(self, instance_name: str) -> List[Dict[str, Any]]:
        """List all EBS volumes attached to a specific EC2 instance by name.

        Args:
            instance_name: Name of the EC2 instance

        Returns:
            List of attached volume information dictionaries
        """
        try:
            # Find the instance by name tag
            response = self.ec2_client.describe_instances(
                Filters=[
                    {"Name": "tag:Name", "Values": [instance_name]},
                    {
                        "Name": "instance-state-name",
                        "Values": ["running", "pending", "stopped", "stopping"],
                    },
                ]
            )

            attached_volumes = []

            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    instance_id = instance["InstanceId"]

                    # Get all block device mappings for this instance
                    for block_device in instance.get("BlockDeviceMappings", []):
                        ebs = block_device.get("Ebs", {})
                        volume_id = ebs.get("VolumeId")

                        if volume_id:
                            # Get detailed volume information
                            volume_response = self.ec2_client.describe_volumes(
                                VolumeIds=[volume_id]
                            )

                            for volume in volume_response["Volumes"]:
                                volume_info = {
                                    "volume_id": volume["VolumeId"],
                                    "device": block_device["DeviceName"],
                                    "size": volume["Size"],
                                    "volume_type": volume["VolumeType"],
                                    "state": volume["State"],
                                    "encrypted": volume.get("Encrypted", False),
                                    "iops": volume.get("Iops", "N/A"),
                                    "creation_time": volume["CreateTime"].strftime(
                                        "%Y-%m-%d %H:%M:%S UTC"
                                    ),
                                    "instance_id": instance_id,
                                    "instance_name": instance_name,
                                }

                                # Add throughput for GP3 volumes
                                if volume["VolumeType"] == "gp3":
                                    volume_info["throughput"] = volume.get(
                                        "Throughput", "N/A"
                                    )

                                attached_volumes.append(volume_info)

            if not attached_volumes:
                self.logger.warning(
                    f"No volumes found attached to instance: {instance_name}"
                )

            return attached_volumes

        except ClientError as e:
            self.logger.error(
                f"Failed to list volumes for instance {instance_name}: {e}"
            )
            raise

    def list_all_volumes(self) -> List[Dict[str, Any]]:
        """List all EBS volumes and their status.

        Returns:
            List of all volume information dictionaries
        """
        try:
            # Get all volumes
            response = self.ec2_client.describe_volumes()

            all_volumes = []

            for volume in response["Volumes"]:
                volume_info = {
                    "volume_id": volume["VolumeId"],
                    "size": volume["Size"],
                    "volume_type": volume["VolumeType"],
                    "state": volume["State"],
                    "encrypted": volume.get("Encrypted", False),
                    "iops": volume.get("Iops", "N/A"),
                    "creation_time": volume["CreateTime"].strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    ),
                    "attached_instance": "N/A",
                    "attached_instance_name": "N/A",
                    "device": "N/A",
                }

                # Add throughput for GP3 volumes
                if volume["VolumeType"] == "gp3":
                    volume_info["throughput"] = volume.get("Throughput", "N/A")

                # Check if volume is attached to an instance
                attachments = volume.get("Attachments", [])
                if attachments:
                    attachment = attachments[
                        0
                    ]  # A volume can only be attached to one instance
                    instance_id = attachment["InstanceId"]
                    volume_info["attached_instance"] = instance_id
                    volume_info["device"] = attachment["Device"]
                    volume_info["state"] = attachment["State"]

                    # Try to get the instance name from tags
                    try:
                        instance_response = self.ec2_client.describe_instances(
                            InstanceIds=[instance_id]
                        )

                        for reservation in instance_response["Reservations"]:
                            for instance in reservation["Instances"]:
                                tags = instance.get("Tags", [])
                                for tag in tags:
                                    if tag["Key"] == "Name":
                                        volume_info["attached_instance_name"] = tag[
                                            "Value"
                                        ]
                                        break

                    except ClientError:
                        # Instance might not exist anymore
                        volume_info["attached_instance_name"] = "Unknown/Deleted"

                all_volumes.append(volume_info)

            return all_volumes

        except ClientError as e:
            self.logger.error(f"Failed to list volumes: {e}")
            raise

    def list_all_snapshots(self) -> List[Dict[str, Any]]:
        """List all EBS snapshots owned by the current account.

        Returns:
            List of snapshot information dictionaries
        """
        try:
            # Get all snapshots owned by this account
            response = self.ec2_client.describe_snapshots(OwnerIds=["self"])

            all_snapshots = []

            for snapshot in response["Snapshots"]:
                snapshot_info = {
                    "snapshot_id": snapshot["SnapshotId"],
                    "description": snapshot.get("Description", "N/A"),
                    "volume_id": snapshot.get("VolumeId", "N/A"),
                    "volume_size": snapshot["VolumeSize"],
                    "state": snapshot["State"],
                    "progress": snapshot.get("Progress", "N/A"),
                    "start_time": snapshot["StartTime"].strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    ),
                    "encrypted": snapshot.get("Encrypted", False),
                }

                # Get tags if any
                tags = snapshot.get("Tags", [])
                for tag in tags:
                    if tag["Key"] == "Name":
                        snapshot_info["name"] = tag["Value"]
                        break
                else:
                    snapshot_info["name"] = "N/A"

                all_snapshots.append(snapshot_info)

            # Sort by start time (newest first)
            all_snapshots.sort(key=lambda x: x["start_time"], reverse=True)

            return all_snapshots

        except ClientError as e:
            self.logger.error(f"Failed to list snapshots: {e}")
            raise


def main():
    """Main function to handle command line arguments and execute the script."""
    parser = argparse.ArgumentParser(
        description="AWS Compute and Storage Automation Script"
    )
    parser.add_argument(
        "action",
        choices=[
            "create",
            "delete",
            "monitor",
            "monitor-alarms",
            "connection-info",
            "list-attached-volumes",
            "list-volumes",
            "list-snapshots",
        ],
        help=(
            "Action to perform: create resources, delete resources, monitor user data execution, "
            "monitor CloudWatch alarms, get connection info, or list resources"
        ),
    )
    parser.add_argument(
        "--spec",
        "-s",
        help=(
            "Path to YAML specification file (required for create, delete, monitor, "
            "monitor-alarms, connection-info actions)"
        ),
    )
    parser.add_argument(
        "--instance-name",
        help="EC2 instance name (required for list-attached-volumes action)",
    )
    parser.add_argument(
        "--region", "-r", default="us-east-1", help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--profile", "-p", help="AWS profile name to use for authentication"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
    )

    args = parser.parse_args()

    # Validate required arguments for different actions
    actions_requiring_spec = [
        "create",
        "delete",
        "monitor",
        "monitor-alarms",
        "connection-info",
    ]
    actions_requiring_instance_name = ["list-attached-volumes"]

    if args.action in actions_requiring_spec and not args.spec:
        parser.error(f"--spec is required for action '{args.action}'")

    if args.action in actions_requiring_instance_name and not args.instance_name:
        parser.error(f"--instance-name is required for action '{args.action}'")

    try:
        spec = None  # Initialize spec
        profile_to_use = args.profile

        # For resource listing commands, we don't need a spec file
        if args.action in ["list-volumes", "list-snapshots", "list-attached-volumes"]:
            manager = AWSResourceManager(region=args.region, profile=profile_to_use)
        else:
            # Load specification first to check for profile in YAML
            with open(args.spec, "r") as f:
                spec = yaml.safe_load(f)

            # Determine which profile to use (command line takes precedence over YAML)
            profile_to_use = args.profile or spec.get("profile")
            manager = AWSResourceManager(region=args.region, profile=profile_to_use)
            spec = manager.load_specification(args.spec)

        if args.dry_run and args.action not in [
            "monitor",
            "monitor-alarms",
            "connection-info",
            "list-attached-volumes",
            "list-volumes",
            "list-snapshots",
        ]:
            if spec is None:
                print("Error: Specification required for dry-run mode")
                return
            print(f"DRY RUN: Would {args.action} resources according to specification:")
            if profile_to_use:
                print(f"Using AWS profile: {profile_to_use}")
            else:
                print("Using default AWS credentials")
            print(yaml.dump(spec, default_flow_style=False))
            return

        if args.action == "create":
            if spec is None:
                print("Error: Specification required for create action")
                return
            resources = manager.provision_resources(spec)
            print(f"Successfully created resources: {resources}")

            # Display connection information
            connection_info = resources.get("connection_info", [])
            if connection_info:
                print("\n" + "=" * 60)
                print("INSTANCE CONNECTION INFORMATION")
                print("=" * 60)
                for info in connection_info:
                    print(f"Instance Name: {info['name']}")
                    print(f"Instance ID: {info['instance_id']}")
                    print(f"Public IP Address: {info['public_ip']}")
                    print(f"State: {info['state']}")
                    if info["public_ip"] != "No public IP":
                        print(
                            f"SSH Command: ssh -i <your-key.pem> ec2-user@{info['public_ip']}"
                        )
                    print("-" * 60)

            # Check if any instances have user data and offer to monitor
            has_user_data = any("user_data" in inst for inst in spec["instances"])
            has_idle_shutdown = any(
                "idle_shutdown" in inst for inst in spec["instances"]
            )

            if has_user_data:
                print("\nInstances with user data scripts detected.")
                print("You can monitor user data execution with:")
                monitor_cmd = f"python script.py monitor --spec {args.spec} --region {args.region}"
                if profile_to_use:
                    monitor_cmd += f" --profile {profile_to_use}"
                print(monitor_cmd)

            if has_idle_shutdown:
                print("\nInstances with idle shutdown alarms detected.")
                print("You can monitor CloudWatch alarms with:")
                monitor_alarm_cmd = f"python script.py monitor-alarms --spec {args.spec} --region {args.region}"
                if profile_to_use:
                    monitor_alarm_cmd += f" --profile {profile_to_use}"
                print(monitor_alarm_cmd)

        elif args.action == "delete":
            if spec is None:
                print("Error: Specification required for delete action")
                return
            manager.delete_resources(spec)
            print("Successfully deleted resources")

        elif args.action == "monitor":
            if spec is None:
                print("Error: Specification required for monitor action")
                return
            logs = manager.monitor_user_data_execution(spec)
            print("\nUser Data Execution Logs:")
            print("=" * 50)
            for instance_name, log_content in logs.items():
                print(f"\nInstance: {instance_name}")
                print("-" * 30)
                print(log_content)
                print("-" * 30)

        elif args.action == "monitor-alarms":
            if spec is None:
                print("Error: Specification required for monitor-alarms action")
                return
            alarm_states = manager.get_cloudwatch_alarms(spec)
            print("\nCloudWatch Idle Shutdown Alarms:")
            print("=" * 50)
            for instance_name, alarm_status in alarm_states.items():
                print(f"Instance: {instance_name}")
                print(f"Status: {alarm_status}")
                print("-" * 30)

        elif args.action == "connection-info":
            if spec is None:
                print("Error: Specification required for connection-info action")
                return
            connection_info = manager.get_connection_info_by_spec(spec)
            print("\n" + "=" * 60)
            print("INSTANCE CONNECTION INFORMATION")
            print("=" * 60)
            if connection_info:
                for info in connection_info:
                    print(f"Instance Name: {info['name']}")
                    print(f"Instance ID: {info['instance_id']}")
                    print(f"Public IP Address: {info['public_ip']}")
                    print(f"State: {info['state']}")
                    if (
                        info["public_ip"] != "No public IP"
                        and info["public_ip"] != "Instance not found"
                    ):
                        print(
                            f"SSH Command: ssh -i <your-key.pem> ec2-user@{info['public_ip']}"
                        )
                    print("-" * 60)
            else:
                print("No instances found matching the specification.")
                print("-" * 60)

        elif args.action == "list-attached-volumes":
            volumes = manager.list_attached_volumes(args.instance_name)
            print(f"\n{'='*80}")
            print(f"VOLUMES ATTACHED TO INSTANCE: {args.instance_name}")
            print(f"{'='*80}")
            if volumes:
                for volume in volumes:
                    print(f"Volume ID: {volume['volume_id']}")
                    print(f"Device: {volume['device']}")
                    print(f"Size: {volume['size']} GB")
                    print(f"Type: {volume['volume_type']}")
                    print(f"State: {volume['state']}")
                    print(f"Encrypted: {volume['encrypted']}")
                    print(f"IOPS: {volume['iops']}")
                    if volume["volume_type"] == "gp3":
                        print(f"Throughput: {volume.get('throughput', 'N/A')} MB/s")
                    print(f"Created: {volume['creation_time']}")
                    print("-" * 80)
            else:
                print(f"No volumes found attached to instance: {args.instance_name}")
                print("-" * 80)

        elif args.action == "list-volumes":
            volumes = manager.list_all_volumes()
            print(f"\n{'='*100}")
            print("ALL EBS VOLUMES")
            print(f"{'='*100}")
            if volumes:
                # Print header
                header = (
                    f"{'Volume ID':<22} {'Size':<6} {'Type':<6} {'State':<12} "
                    f"{'Encrypted':<10} {'Instance':<19} {'Instance Name':<20} {'Device':<12}"
                )
                print(header)
                print("-" * 100)

                for volume in volumes:
                    encrypted = "Yes" if volume["encrypted"] else "No"
                    instance_id = volume["attached_instance"]
                    if instance_id != "N/A":
                        instance_id = instance_id[
                            -8:
                        ]  # Show last 8 chars of instance ID

                    instance_name = volume["attached_instance_name"]
                    if len(instance_name) > 18:
                        instance_name = instance_name[:15] + "..."

                    device = volume["device"]
                    if len(device) > 10:
                        device = device[:7] + "..."

                    row = (
                        f"{volume['volume_id']:<22} {volume['size']:<6} "
                        f"{volume['volume_type']:<6} {volume['state']:<12} "
                        f"{encrypted:<10} {instance_id:<19} "
                        f"{instance_name:<20} {device:<12}"
                    )
                    print(row)

                print("-" * 100)
                print(f"Total volumes: {len(volumes)}")
            else:
                print("No volumes found.")
                print("-" * 100)

        elif args.action == "list-snapshots":
            snapshots = manager.list_all_snapshots()
            print(f"\n{'='*120}")
            print("ALL EBS SNAPSHOTS")
            print(f"{'='*120}")
            if snapshots:
                # Print header
                header = (
                    f"{'Snapshot ID':<22} {'Name':<25} {'Volume ID':<22} "
                    f"{'Size':<6} {'State':<12} {'Progress':<10} "
                    f"{'Start Time':<20} {'Encrypted':<10}"
                )
                print(header)
                print("-" * 120)

                for snapshot in snapshots:
                    encrypted = "Yes" if snapshot["encrypted"] else "No"
                    name = snapshot["name"]
                    if len(name) > 23:
                        name = name[:20] + "..."

                    progress = snapshot["progress"]
                    if progress != "N/A" and len(progress) > 8:
                        progress = progress[:8]

                    row = (
                        f"{snapshot['snapshot_id']:<22} {name:<25} "
                        f"{snapshot['volume_id']:<22} {snapshot['volume_size']:<6} "
                        f"{snapshot['state']:<12} {progress:<10} "
                        f"{snapshot['start_time']:<20} {encrypted:<10}"
                    )
                    print(row)

                print("-" * 120)
                print(f"Total snapshots: {len(snapshots)}")
            else:
                print("No snapshots found.")
                print("-" * 120)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def date():
    """Return current datetime (kept for compatibility with existing tests)."""
    current_datetime = datetime.now()
    return current_datetime


if __name__ == "__main__":
    main()

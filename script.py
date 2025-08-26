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
from typing import Dict, List, Any
import yaml
import boto3
from botocore.exceptions import ClientError


class AWSResourceManager:
    """Manages AWS EC2 instances and EBS volumes with idempotency and rollback support."""

    def __init__(self, region: str = "us-east-1", profile: str = None):
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
            self.logger.info("Using default AWS credentials (environment variables or default profile)")
        
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
                    raise ValueError(f"Cannot specify both script_path and inline_script in instance {i}")
                
                if "script_path" not in user_data and "inline_script" not in user_data:
                    raise ValueError(f"user_data must contain either script_path or inline_script in instance {i}")

            # Validate idle shutdown configuration
            if "idle_shutdown" in instance:
                idle_config = instance["idle_shutdown"]
                if not isinstance(idle_config, dict):
                    raise ValueError(f"idle_shutdown must be an object in instance {i}")
                
                required_idle_fields = ["cpu_threshold", "evaluation_minutes"]
                for field in required_idle_fields:
                    if field not in idle_config:
                        raise ValueError(f"Missing required field '{field}' in idle_shutdown config for instance {i}")
                
                # Validate threshold is between 0 and 100
                threshold = idle_config["cpu_threshold"]
                if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 100:
                    raise ValueError(f"cpu_threshold must be a number between 0 and 100 in instance {i}")
                
                # Validate evaluation_minutes is positive
                eval_mins = idle_config["evaluation_minutes"]
                if not isinstance(eval_mins, int) or eval_mins <= 0:
                    raise ValueError(f"evaluation_minutes must be a positive integer in instance {i}")
                
                # Validate action if specified
                if "action" in idle_config:
                    valid_actions = ["stop", "terminate"]
                    if idle_config["action"] not in valid_actions:
                        raise ValueError(f"idle_shutdown action must be one of {valid_actions} in instance {i}")

        self.logger.info("Specification validation passed")

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

    def _prepare_user_data(self, instance_spec: Dict[str, Any]) -> str:
        """Prepare user data script for instance.

        Args:
            instance_spec: Instance specification containing user data

        Returns:
            User data script content (base64 will be handled by boto3)

        Raises:
            FileNotFoundError: If script file doesn't exist
            Exception: If script preparation fails
        """
        if "user_data" not in instance_spec:
            return ""

        user_data = instance_spec["user_data"]
        
        try:
            if "script_path" in user_data:
                # Load script from file
                script_path = user_data["script_path"]
                with open(script_path, "r") as f:
                    script_content = f.read()
                self.logger.info(f"Loaded user data script from {script_path}")
            elif "inline_script" in user_data:
                # Use inline script content
                script_content = user_data["inline_script"]
                self.logger.info("Using inline user data script")
            else:
                return ""

            # Add logging wrapper to capture user data execution
            wrapper_script = f'''#!/bin/bash
# AWS Automation Script - User Data Execution
# Instance: {instance_spec["name"]}
# Generated: {datetime.now().isoformat()}

LOG_FILE="/var/log/user-data-execution.log"
exec > >(tee -a $LOG_FILE)
exec 2>&1

echo "===== User Data Script Execution Started ====="
echo "Timestamp: $(date)"
echo "Instance Name: {instance_spec["name"]}"
echo "=============================================="

# Original user script
{script_content}

echo "=============================================="
echo "User Data Script Execution Completed"
echo "Timestamp: $(date)"
echo "Exit Code: $?"
echo "=============================================="
'''

            return wrapper_script

        except FileNotFoundError:
            self.logger.error(f"User data script file not found: {user_data.get('script_path')}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to prepare user data script: {e}")
            raise

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
            self.logger.info(f"Added user data script to instance {instance_spec['name']}")

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

    def _create_idle_shutdown_alarm(self, instance_id: str, instance_spec: Dict[str, Any]) -> str:
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
        alarm_description = f"Idle shutdown alarm for {instance_name} - {action} instance when CPU < {cpu_threshold}% for {evaluation_minutes} minutes"
        
        try:
            # Check if alarm already exists (for idempotency)
            try:
                existing_alarms = self.cloudwatch_client.describe_alarms(AlarmNames=[alarm_name])
                if existing_alarms.get("MetricAlarms"):
                    self.logger.info(f"CloudWatch alarm {alarm_name} already exists, skipping creation")
                    return alarm_name
            except ClientError:
                # Alarm doesn't exist, proceed with creation
                pass
            
            # Create the alarm
            self.cloudwatch_client.put_metric_alarm(
                AlarmName=alarm_name,
                AlarmDescription=alarm_description,
                ActionsEnabled=True,
                AlarmActions=[
                    f"arn:aws:automate:{self.region}:ec2:{action}"
                ],
                MetricName="CPUUtilization",
                Namespace="AWS/EC2",
                Statistic="Average",
                Dimensions=[
                    {
                        "Name": "InstanceId",
                        "Value": instance_id
                    }
                ],
                Period=300,  # 5 minutes
                EvaluationPeriods=evaluation_minutes // 5,  # Convert minutes to 5-minute periods
                Threshold=cpu_threshold,
                ComparisonOperator="LessThanThreshold",
                TreatMissingData="notBreaching"  # Don't shutdown when missing data (e.g., during startup)
            )
            
            self.logger.info(f"Created CloudWatch alarm: {alarm_name} for instance {instance_id}")
            self.created_resources["alarms"].append(alarm_name)
            return alarm_name
            
        except ClientError as e:
            self.logger.error(f"Failed to create CloudWatch alarm for instance {instance_id}: {e}")
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
                "connection_info": connection_info
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
                alarm_name = self._create_idle_shutdown_alarm(instance_id, instance_spec)
                if alarm_name:
                    provisioned["alarms"].append(alarm_name)

            # Get connection information for all provisioned instances
            connection_info = self.get_instance_connection_info(provisioned["instances"])
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
                self.logger.warning(f"Failed to delete CloudWatch alarm {alarm_name}: {e}")

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
                    response = self.cloudwatch_client.describe_alarms(AlarmNames=alarms_to_delete)
                    existing_alarms = [alarm["AlarmName"] for alarm in response["MetricAlarms"]]
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

        # Delete volumes (they should be automatically deleted when instances are terminated if DeleteOnTermination is True)
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
            response = self.ec2_client.get_console_output(InstanceId=instance_id, Latest=True)
            console_output = response.get("Output", "")
            
            self.logger.info(f"Retrieved console output for instance {instance_id}")
            
            # Extract user data related logs
            if "User Data Script Execution" in console_output:
                lines = console_output.split('\n')
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
                
                return '\n'.join(user_data_logs)
            else:
                return "No user data execution logs found in console output."
                
        except ClientError as e:
            self.logger.error(f"Failed to retrieve console output for {instance_id}: {e}")
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
                            self.logger.info(f"Retrieved user data logs for {instance_name} ({instance_id})")
                        except Exception as e:
                            logs[instance_name] = f"Failed to retrieve logs: {e}"
                            self.logger.error(f"Failed to retrieve user data logs for {instance_name}: {e}")
                            
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
                                alarm_states[instance_name] = f"Alarm: {state} - {reason}"
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

    def get_instance_connection_info(self, instance_ids: List[str]) -> List[Dict[str, str]]:
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
                    
                    connection_info.append({
                        "instance_id": instance_id,
                        "name": instance_name,
                        "public_ip": public_ip,
                        "state": instance["State"]["Name"]
                    })
                    
            self.logger.info(f"Retrieved connection information for {len(connection_info)} instances")
            return connection_info
            
        except ClientError as e:
            self.logger.error(f"Failed to retrieve instance connection information: {e}")
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
                        
                        all_connection_info.append({
                            "instance_id": instance_id,
                            "name": instance_name,
                            "public_ip": public_ip,
                            "state": instance["State"]["Name"]
                        })
                        
            except ClientError as e:
                self.logger.error(f"Failed to find instance {instance_name}: {e}")
                # Add entry indicating instance not found
                all_connection_info.append({
                    "instance_id": "N/A",
                    "name": instance_name,
                    "public_ip": "Instance not found",
                    "state": "unknown"
                })
        
        return all_connection_info


def main():
    """Main function to handle command line arguments and execute the script."""
    parser = argparse.ArgumentParser(
        description="AWS Compute and Storage Automation Script"
    )
    parser.add_argument(
        "action", 
        choices=["create", "delete", "monitor", "monitor-alarms", "connection-info"], 
        help="Action to perform: create resources, delete resources, monitor user data execution, monitor CloudWatch alarms, or get connection info"
    )
    parser.add_argument(
        "--spec", "-s", required=True, help="Path to YAML specification file"
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

    try:
        # Load specification first to check for profile in YAML
        with open(args.spec, "r") as f:
            spec = yaml.safe_load(f)
        
        # Determine which profile to use (command line takes precedence over YAML)
        profile_to_use = args.profile or spec.get("profile")
        
        manager = AWSResourceManager(region=args.region, profile=profile_to_use)
        spec = manager.load_specification(args.spec)

        if args.dry_run and args.action not in ["monitor", "monitor-alarms", "connection-info"]:
            print(f"DRY RUN: Would {args.action} resources according to specification:")
            if profile_to_use:
                print(f"Using AWS profile: {profile_to_use}")
            else:
                print("Using default AWS credentials")
            print(yaml.dump(spec, default_flow_style=False))
            return

        if args.action == "create":
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
                    if info['public_ip'] != "No public IP":
                        print(f"SSH Command: ssh -i <your-key.pem> ec2-user@{info['public_ip']}")
                    print("-" * 60)
            
            # Check if any instances have user data and offer to monitor
            has_user_data = any("user_data" in inst for inst in spec["instances"])
            has_idle_shutdown = any("idle_shutdown" in inst for inst in spec["instances"])
            
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
            manager.delete_resources(spec)
            print("Successfully deleted resources")
            
        elif args.action == "monitor":
            logs = manager.monitor_user_data_execution(spec)
            print("\nUser Data Execution Logs:")
            print("=" * 50)
            for instance_name, log_content in logs.items():
                print(f"\nInstance: {instance_name}")
                print("-" * 30)
                print(log_content)
                print("-" * 30)
                
        elif args.action == "monitor-alarms":
            alarm_states = manager.get_cloudwatch_alarms(spec)
            print("\nCloudWatch Idle Shutdown Alarms:")
            print("=" * 50)
            for instance_name, alarm_status in alarm_states.items():
                print(f"Instance: {instance_name}")
                print(f"Status: {alarm_status}")
                print("-" * 30)
                
        elif args.action == "connection-info":
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
                    if info['public_ip'] != "No public IP" and info['public_ip'] != "Instance not found":
                        print(f"SSH Command: ssh -i <your-key.pem> ec2-user@{info['public_ip']}")
                    print("-" * 60)
            else:
                print("No instances found matching the specification.")
                print("-" * 60)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def date():
    """Return current datetime (kept for compatibility with existing tests)."""
    current_datetime = datetime.now()
    return current_datetime


if __name__ == "__main__":
    main()

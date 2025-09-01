import pytest
import yaml
from unittest.mock import patch, MagicMock
from script import AWSResourceManager


class TestAWSResourceManager:
    """Test cases for the AWSResourceManager class."""

    @pytest.fixture
    def sample_spec(self):
        """Sample specification for testing."""
        return {
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "market_type": "on-demand",
                    "key_name": "test-key",
                    "security_groups": ["sg-12345678"],
                    "volumes": [
                        {
                            "size": 20,
                            "type": "gp3",
                            "device": "/dev/sdf",
                            "encrypted": True,
                        }
                    ],
                }
            ]
        }

    @pytest.fixture
    def aws_manager(self):
        """Create an AWSResourceManager instance with mocked AWS clients."""
        with patch("boto3.Session") as mock_session:
            mock_session.return_value.client.return_value = MagicMock()
            mock_session.return_value.resource.return_value = MagicMock()
            manager = AWSResourceManager(region="us-east-1")
            return manager

    @pytest.fixture
    def aws_manager_with_profile(self):
        """Create an AWSResourceManager instance with profile and mocked AWS clients."""
        with patch("boto3.Session") as mock_session:
            mock_session.return_value.client.return_value = MagicMock()
            mock_session.return_value.resource.return_value = MagicMock()
            manager = AWSResourceManager(region="us-east-1", profile="test-profile")
            return manager

    def test_specification_validation_valid(self, aws_manager, sample_spec):
        """Test that valid specifications pass validation."""
        # Should not raise any exception
        aws_manager._validate_specification(sample_spec)

    def test_specification_validation_missing_instances(self, aws_manager):
        """Test that specifications without instances field fail validation."""
        invalid_spec = {"other_field": "value"}

        with pytest.raises(
            ValueError, match="Missing required field in specification: instances"
        ):
            aws_manager._validate_specification(invalid_spec)

    def test_specification_validation_missing_instance_fields(self, aws_manager):
        """Test that instances without required fields fail validation."""
        invalid_spec = {
            "instances": [
                {
                    "name": "test-instance",
                    # missing instance_type and ami_id
                }
            ]
        }

        with pytest.raises(ValueError, match="Missing required field"):
            aws_manager._validate_specification(invalid_spec)

    def test_specification_validation_invalid_iam_role(self, aws_manager):
        """Test that invalid IAM role configurations fail validation."""
        # Test empty string IAM role
        invalid_spec_empty = {
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "iam_role": "",
                }
            ]
        }

        with pytest.raises(ValueError, match="iam_role must be a non-empty string"):
            aws_manager._validate_specification(invalid_spec_empty)

        # Test non-string IAM role
        invalid_spec_non_string = {
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "iam_role": 123,
                }
            ]
        }

        with pytest.raises(ValueError, match="iam_role must be a non-empty string"):
            aws_manager._validate_specification(invalid_spec_non_string)

    def test_specification_validation_valid_iam_role(self, aws_manager):
        """Test that valid IAM role configurations pass validation."""
        valid_spec = {
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "iam_role": "my-instance-role",
                }
            ]
        }

        # Should not raise any exception
        aws_manager._validate_specification(valid_spec)

    def test_load_specification_file_not_found(self, aws_manager):
        """Test that loading non-existent specification file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            aws_manager.load_specification("non_existent_file.yaml")

    @patch("builtins.open")
    @patch("yaml.safe_load")
    def test_load_specification_yaml_error(
        self, mock_yaml_load, mock_open, aws_manager
    ):
        """Test that invalid YAML raises appropriate error."""
        mock_yaml_load.side_effect = yaml.YAMLError("Invalid YAML")

        with pytest.raises(yaml.YAMLError):
            aws_manager.load_specification("test.yaml")

    @patch("builtins.open")
    @patch("yaml.safe_load")
    def test_load_specification_success(
        self, mock_yaml_load, mock_open, aws_manager, sample_spec
    ):
        """Test successful specification loading."""
        mock_yaml_load.return_value = sample_spec
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        result = aws_manager.load_specification("test.yaml")

        assert result == sample_spec
        mock_open.assert_called_once_with("test.yaml", "r")
        mock_yaml_load.assert_called_once_with(mock_file)

    def test_aws_manager_with_profile(self, aws_manager_with_profile):
        """Test that AWSResourceManager correctly initializes with a profile."""
        assert aws_manager_with_profile.profile == "test-profile"
        assert aws_manager_with_profile.region == "us-east-1"

    def test_aws_manager_without_profile(self, aws_manager):
        """Test that AWSResourceManager correctly initializes without a profile."""
        assert aws_manager.profile is None
        assert aws_manager.region == "us-east-1"

    def test_specification_validation_with_valid_profile(self, aws_manager):
        """Test that specifications with valid profile pass validation."""
        spec_with_profile = {
            "profile": "my-test-profile",
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                }
            ],
        }
        # Should not raise any exception
        aws_manager._validate_specification(spec_with_profile)

    def test_specification_validation_with_invalid_profile(self, aws_manager):
        """Test that specifications with invalid profile type fail validation."""
        spec_with_invalid_profile = {
            "profile": 123,  # Should be string, not int
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                }
            ],
        }

        with pytest.raises(ValueError, match="Profile field must be a string"):
            aws_manager._validate_specification(spec_with_invalid_profile)

    @patch("boto3.Session")
    def test_profile_usage_in_constructor(self, mock_session):
        """Test that profile is correctly passed to boto3.Session."""
        # Test with profile
        AWSResourceManager(region="us-west-2", profile="test-profile")
        mock_session.assert_called_with(profile_name="test-profile")

        # Reset mock
        mock_session.reset_mock()

        # Test without profile
        AWSResourceManager(region="us-west-2", profile=None)
        mock_session.assert_called_with()


class TestSpecificationValidation:
    """Test cases for YAML specification validation."""

    def test_minimal_valid_spec(self):
        """Test that minimal valid specification is accepted."""
        spec = {
            "instances": [
                {"name": "test", "instance_type": "t3.micro", "ami_id": "ami-12345678"}
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            manager._validate_specification(spec)  # Should not raise

    def test_spot_instance_configuration(self):
        """Test that spot instance configuration is properly structured."""
        spec = {
            "instances": [
                {
                    "name": "spot-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "market_type": "spot",
                    "spot_price": "0.02",
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            manager._validate_specification(spec)  # Should not raise

    def test_volume_configuration(self):
        """Test that volume configuration is properly structured."""
        spec = {
            "instances": [
                {
                    "name": "storage-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "volumes": [
                        {
                            "size": 100,
                            "type": "gp3",
                            "device": "/dev/sdf",
                            "iops": 3000,
                            "encrypted": True,
                        },
                        {
                            "size": 50,
                            "type": "io2",
                            "device": "/dev/sdg",
                            "iops": 1000,
                            "encrypted": False,
                        },
                    ],
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            manager._validate_specification(spec)  # Should not raise

    def test_user_data_script_path_configuration(self):
        """Test that user data with script_path is properly validated."""
        spec = {
            "instances": [
                {
                    "name": "user-data-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "user_data": {"script_path": "examples/python_web_server.sh"},
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            manager._validate_specification(spec)  # Should not raise

    def test_user_data_inline_script_configuration(self):
        """Test that user data with inline_script is properly validated."""
        spec = {
            "instances": [
                {
                    "name": "user-data-inline-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "user_data": {"inline_script": "#!/bin/bash\nyum update -y\n"},
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            manager._validate_specification(spec)  # Should not raise

    def test_user_data_both_script_and_inline_fails(self):
        """Test that user data with both script_path and inline_script fails validation."""
        spec = {
            "instances": [
                {
                    "name": "user-data-invalid-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "user_data": {
                        "script_path": "script.sh",
                        "inline_script": "#!/bin/bash\necho 'test'",
                    },
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            with pytest.raises(
                ValueError, match="Cannot specify both script_path and inline_script"
            ):
                manager._validate_specification(spec)

    def test_user_data_empty_fails(self):
        """Test that empty user data fails validation."""
        spec = {
            "instances": [
                {
                    "name": "user-data-empty-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "user_data": {},
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            with pytest.raises(
                ValueError,
                match="user_data must contain either script_path or inline_script",
            ):
                manager._validate_specification(spec)

    def test_user_data_invalid_type_fails(self):
        """Test that user data with wrong type fails validation."""
        spec = {
            "instances": [
                {
                    "name": "user-data-type-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "user_data": "this should be an object, not a string",
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            with pytest.raises(ValueError, match="user_data must be an object"):
                manager._validate_specification(spec)

    def test_iam_role_configuration(self):
        """Test that IAM role configuration is properly validated."""
        spec = {
            "instances": [
                {
                    "name": "iam-role-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "iam_role": "my-instance-role",
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            manager._validate_specification(spec)  # Should not raise

    def test_iam_role_empty_string_fails(self):
        """Test that empty IAM role string fails validation."""
        spec = {
            "instances": [
                {
                    "name": "iam-role-empty-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "iam_role": "",
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            with pytest.raises(ValueError, match="iam_role must be a non-empty string"):
                manager._validate_specification(spec)

    def test_iam_role_non_string_fails(self):
        """Test that non-string IAM role fails validation."""
        spec = {
            "instances": [
                {
                    "name": "iam-role-non-string-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "iam_role": 123,
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            with pytest.raises(ValueError, match="iam_role must be a non-empty string"):
                manager._validate_specification(spec)


class TestUserDataPrepation:
    """Test cases for user data script preparation."""

    @pytest.fixture
    def aws_manager(self):
        """Create an AWSResourceManager instance with mocked AWS clients."""
        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager(region="us-east-1")
            return manager

    # TODO: confirm the need for this this test
    # with the introduction of mounting EBS, an empty user data script may  no longer be an issue
    # since the user data script will, at minimum, have code to do the mounting
    # def test_prepare_user_data_no_user_data(self, aws_manager):
    #     """Test user data preparation when no user data is specified."""
    #     instance_spec = {
    #         "name": "test-instance",
    #         "instance_type": "t3.micro",
    #         "ami_id": "ami-12345678",
    #     }

    #     result = aws_manager._prepare_user_data(instance_spec)
    #     assert result == ""

    @patch("builtins.open")
    def test_prepare_user_data_from_file(self, mock_open, aws_manager):
        """Test user data preparation from script file."""
        instance_spec = {
            "name": "test-instance",
            "instance_type": "t3.micro",
            "ami_id": "ami-12345678",
            "user_data": {"script_path": "test_script.sh"},
        }

        mock_file = MagicMock()
        mock_file.read.return_value = "#!/bin/bash\necho 'test script'"
        mock_open.return_value.__enter__.return_value = mock_file

        result = aws_manager._prepare_user_data(instance_spec)

        assert "#!/bin/bash" in result
        assert "test script" in result
        assert "User Data Script Execution Started" in result
        assert instance_spec["name"] in result
        mock_open.assert_called_once_with("test_script.sh", "r")

    def test_prepare_user_data_inline(self, aws_manager):
        """Test user data preparation from inline script."""
        instance_spec = {
            "name": "test-instance",
            "instance_type": "t3.micro",
            "ami_id": "ami-12345678",
            "user_data": {"inline_script": "#!/bin/bash\necho 'inline test'"},
        }

        result = aws_manager._prepare_user_data(instance_spec)

        assert "#!/bin/bash" in result
        assert "inline test" in result
        assert "User Data Script Execution Started" in result
        assert instance_spec["name"] in result

    def test_validate_idle_shutdown_config(self, aws_manager):
        """Test validation of idle shutdown configuration."""
        # Valid configuration
        valid_spec = {
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "idle_shutdown": {
                        "cpu_threshold": 10.0,
                        "evaluation_minutes": 15,
                        "action": "stop",
                    },
                }
            ]
        }

        # Should not raise an exception
        aws_manager._validate_specification(valid_spec)

        # Invalid threshold (out of range)
        invalid_spec = {
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "idle_shutdown": {
                        "cpu_threshold": 150.0,  # Invalid: > 100
                        "evaluation_minutes": 15,
                    },
                }
            ]
        }

        with pytest.raises(
            ValueError, match="cpu_threshold must be a number between 0 and 100"
        ):
            aws_manager._validate_specification(invalid_spec)

        # Invalid evaluation_minutes (negative)
        invalid_spec2 = {
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "idle_shutdown": {
                        "cpu_threshold": 10.0,
                        "evaluation_minutes": -5,  # Invalid: negative
                    },
                }
            ]
        }

        with pytest.raises(
            ValueError, match="evaluation_minutes must be a positive integer"
        ):
            aws_manager._validate_specification(invalid_spec2)

    def test_create_idle_shutdown_alarm(self, aws_manager):
        """Test CloudWatch alarm creation for idle shutdown."""
        instance_spec = {
            "name": "test-instance",
            "idle_shutdown": {
                "cpu_threshold": 10.0,
                "evaluation_minutes": 15,
                "action": "stop",
            },
        }

        instance_id = "i-1234567890abcdef0"
        expected_alarm_name = f"idle-shutdown-{instance_spec['name']}-{instance_id}"

        # Mock CloudWatch client methods
        aws_manager.cloudwatch_client.put_metric_alarm = MagicMock()
        aws_manager.cloudwatch_client.describe_alarms = MagicMock(
            return_value={"MetricAlarms": []}
        )

        result = aws_manager._create_idle_shutdown_alarm(instance_id, instance_spec)

        assert result == expected_alarm_name
        assert expected_alarm_name in aws_manager.created_resources["alarms"]

        # Verify the CloudWatch API call
        aws_manager.cloudwatch_client.put_metric_alarm.assert_called_once()
        call_args = aws_manager.cloudwatch_client.put_metric_alarm.call_args[1]

        assert call_args["AlarmName"] == expected_alarm_name
        assert call_args["MetricName"] == "CPUUtilization"
        assert call_args["Threshold"] == 10.0
        assert call_args["ComparisonOperator"] == "LessThanThreshold"
        assert call_args["EvaluationPeriods"] == 3  # 15 minutes / 5 minute periods
        assert call_args["TreatMissingData"] == "notBreaching"  # Startup protection
        assert "ec2:stop" in call_args["AlarmActions"][0]

    def test_create_idle_shutdown_alarm_terminate(self, aws_manager):
        """Test CloudWatch alarm creation with terminate action."""
        instance_spec = {
            "name": "test-instance",
            "idle_shutdown": {
                "cpu_threshold": 5.0,
                "evaluation_minutes": 10,
                "action": "terminate",
            },
        }

        instance_id = "i-1234567890abcdef0"

        # Mock CloudWatch client methods
        aws_manager.cloudwatch_client.put_metric_alarm = MagicMock()
        aws_manager.cloudwatch_client.describe_alarms = MagicMock(
            return_value={"MetricAlarms": []}
        )

        aws_manager._create_idle_shutdown_alarm(instance_id, instance_spec)

        # Verify the action is terminate
        call_args = aws_manager.cloudwatch_client.put_metric_alarm.call_args[1]
        assert call_args["TreatMissingData"] == "notBreaching"  # Startup protection
        assert "ec2:terminate" in call_args["AlarmActions"][0]

    def test_create_idle_shutdown_alarm_no_config(self, aws_manager):
        """Test that no alarm is created when idle_shutdown is not configured."""
        instance_spec = {
            "name": "test-instance",
            "instance_type": "t3.micro",
            "ami_id": "ami-12345678",
        }

        instance_id = "i-1234567890abcdef0"

        # Mock CloudWatch client methods
        aws_manager.cloudwatch_client.put_metric_alarm = MagicMock()

        result = aws_manager._create_idle_shutdown_alarm(instance_id, instance_spec)

        assert result is None
        assert len(aws_manager.created_resources["alarms"]) == 0
        aws_manager.cloudwatch_client.put_metric_alarm.assert_not_called()


class TestConnectionInformation:
    """Test cases for connection information functionality."""

    @pytest.fixture
    def aws_manager(self):
        """Create an AWSResourceManager instance with mocked AWS clients."""
        with patch("boto3.Session") as mock_session:
            mock_session.return_value.client.return_value = MagicMock()
            mock_session.return_value.resource.return_value = MagicMock()
            manager = AWSResourceManager(region="us-east-1")
            return manager

    def test_get_instance_connection_info(self, aws_manager):
        """Test getting connection information for instances."""
        # Mock the describe_instances response
        mock_response = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-12345678",
                            "PublicIpAddress": "54.123.45.67",
                            "State": {"Name": "running"},
                            "Tags": [
                                {"Key": "Name", "Value": "test-instance-1"},
                                {"Key": "Environment", "Value": "test"},
                            ],
                        }
                    ]
                },
                {
                    "Instances": [
                        {
                            "InstanceId": "i-87654321",
                            "State": {"Name": "running"},
                            "Tags": [{"Key": "Name", "Value": "test-instance-2"}],
                            # No PublicIpAddress key - should default to "No public IP"
                        }
                    ]
                },
            ]
        }

        aws_manager.ec2_client.describe_instances.return_value = mock_response

        instance_ids = ["i-12345678", "i-87654321"]
        result = aws_manager.get_instance_connection_info(instance_ids)

        assert len(result) == 2

        # Check first instance
        assert result[0]["instance_id"] == "i-12345678"
        assert result[0]["name"] == "test-instance-1"
        assert result[0]["public_ip"] == "54.123.45.67"
        assert result[0]["state"] == "running"

        # Check second instance (no public IP)
        assert result[1]["instance_id"] == "i-87654321"
        assert result[1]["name"] == "test-instance-2"
        assert result[1]["public_ip"] == "No public IP"
        assert result[1]["state"] == "running"

        aws_manager.ec2_client.describe_instances.assert_called_once_with(
            InstanceIds=instance_ids
        )

    def test_get_instance_connection_info_empty_list(self, aws_manager):
        """Test getting connection information with empty instance list."""
        result = aws_manager.get_instance_connection_info([])

        assert result == []
        aws_manager.ec2_client.describe_instances.assert_not_called()

    def test_get_connection_info_by_spec(self, aws_manager):
        """Test getting connection information by specification."""
        spec = {"instances": [{"name": "web-server"}, {"name": "app-server"}]}

        # Mock responses for each instance lookup
        def mock_describe_instances(**kwargs):
            filters = kwargs.get("Filters", [])
            name_filter = next((f for f in filters if f["Name"] == "tag:Name"), None)
            if name_filter:
                instance_name = name_filter["Values"][0]
                if instance_name == "web-server":
                    return {
                        "Reservations": [
                            {
                                "Instances": [
                                    {
                                        "InstanceId": "i-web123",
                                        "PublicIpAddress": "1.2.3.4",
                                        "State": {"Name": "running"},
                                    }
                                ]
                            }
                        ]
                    }
                elif instance_name == "app-server":
                    return {
                        "Reservations": [
                            {
                                "Instances": [
                                    {
                                        "InstanceId": "i-app456",
                                        "State": {"Name": "stopped"},
                                        # No PublicIpAddress
                                    }
                                ]
                            }
                        ]
                    }
            return {"Reservations": []}

        aws_manager.ec2_client.describe_instances.side_effect = mock_describe_instances

        result = aws_manager.get_connection_info_by_spec(spec)

        assert len(result) == 2
        assert result[0]["name"] == "web-server"
        assert result[0]["instance_id"] == "i-web123"
        assert result[0]["public_ip"] == "1.2.3.4"
        assert result[0]["state"] == "running"

        assert result[1]["name"] == "app-server"
        assert result[1]["instance_id"] == "i-app456"
        assert result[1]["public_ip"] == "No public IP"
        assert result[1]["state"] == "stopped"

    def test_provision_resources_includes_connection_info(self, aws_manager):
        """Test that provision_resources returns connection information."""
        spec = {
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                }
            ]
        }

        # Mock _get_existing_resources to return no existing resources
        aws_manager._get_existing_resources = MagicMock(
            return_value={"instances": [], "volumes": [], "alarms": []}
        )

        # Mock _create_ec2_instance
        aws_manager._create_ec2_instance = MagicMock(return_value="i-123456789")

        # Mock _create_and_attach_volumes
        aws_manager._create_and_attach_volumes = MagicMock(return_value=[])

        # Mock _create_idle_shutdown_alarm
        aws_manager._create_idle_shutdown_alarm = MagicMock(return_value=None)

        # Mock get_instance_connection_info
        mock_connection_info = [
            {
                "instance_id": "i-123456789",
                "name": "test-instance",
                "public_ip": "1.2.3.4",
                "state": "running",
            }
        ]
        aws_manager.get_instance_connection_info = MagicMock(
            return_value=mock_connection_info
        )

        result = aws_manager.provision_resources(spec)

        assert "connection_info" in result
        assert result["connection_info"] == mock_connection_info
        assert len(result["instances"]) == 1
        assert result["instances"][0] == "i-123456789"


class TestIAMRoleInstanceCreation:
    """Test cases for IAM role instance creation."""

    @pytest.fixture
    def aws_manager(self):
        """Create an AWSResourceManager instance with mocked AWS clients."""
        with patch("boto3.Session") as mock_session:
            mock_session.return_value.client.return_value = MagicMock()
            mock_session.return_value.resource.return_value = MagicMock()
            manager = AWSResourceManager(region="us-east-1")
            return manager

    def test_create_instance_with_iam_role(self, aws_manager):
        """Test that IAM instance profile is correctly added to run_instances call."""
        instance_spec = {
            "name": "test-iam-instance",
            "instance_type": "t3.micro",
            "ami_id": "ami-12345678",
            "iam_role": "my-instance-role",
        }

        # Mock the run_instances response
        mock_response = {
            "Instances": [
                {"InstanceId": "i-1234567890abcdef0", "State": {"Name": "pending"}}
            ]
        }
        aws_manager.ec2_client.run_instances.return_value = mock_response

        # Mock the waiter
        mock_waiter = MagicMock()
        aws_manager.ec2_client.get_waiter.return_value = mock_waiter

        # Call the method
        instance_id = aws_manager._create_ec2_instance(instance_spec)

        # Verify the run_instances call included IAM instance profile
        aws_manager.ec2_client.run_instances.assert_called_once()
        call_args = aws_manager.ec2_client.run_instances.call_args[1]

        assert "IamInstanceProfile" in call_args
        assert call_args["IamInstanceProfile"]["Name"] == "my-instance-role"
        assert instance_id == "i-1234567890abcdef0"

    def test_create_instance_without_iam_role(self, aws_manager):
        """Test that IAM instance profile is not added when not specified."""
        instance_spec = {
            "name": "test-no-iam-instance",
            "instance_type": "t3.micro",
            "ami_id": "ami-12345678",
        }

        # Mock the run_instances response
        mock_response = {
            "Instances": [
                {"InstanceId": "i-1234567890abcdef1", "State": {"Name": "pending"}}
            ]
        }
        aws_manager.ec2_client.run_instances.return_value = mock_response

        # Mock the waiter
        mock_waiter = MagicMock()
        aws_manager.ec2_client.get_waiter.return_value = mock_waiter

        # Call the method
        instance_id = aws_manager._create_ec2_instance(instance_spec)

        # Verify the run_instances call did not include IAM instance profile
        aws_manager.ec2_client.run_instances.assert_called_once()
        call_args = aws_manager.ec2_client.run_instances.call_args[1]

        assert "IamInstanceProfile" not in call_args
        assert instance_id == "i-1234567890abcdef1"


class TestVolumeMountPoints:
    """Test cases for the new mount point functionality."""

    @pytest.fixture
    def aws_manager(self):
        """Create an AWSResourceManager instance with mocked AWS clients."""
        with patch("boto3.Session") as mock_session:
            mock_session.return_value.client.return_value = MagicMock()
            mock_session.return_value.resource.return_value = MagicMock()
            manager = AWSResourceManager(region="us-east-1")
            return manager

    def test_validate_volume_spec_with_mount_point(self, aws_manager):
        """Test volume specification validation with mount points."""
        # Valid volume spec with mount point
        valid_volume = {
            "size": 50,
            "type": "gp3",
            "device": "/dev/sdf",
            "mount_point": "/data",
            "filesystem": "ext4",
            "mount_options": "defaults,noatime",
        }

        # Should not raise any exception
        aws_manager._validate_volume_spec(valid_volume, 0, 0)

    def test_validate_volume_spec_invalid_mount_point(self, aws_manager):
        """Test volume specification validation with invalid mount points."""
        # Test non-absolute path
        invalid_volume_relative = {
            "size": 50,
            "mount_point": "data",  # Should start with /
        }

        with pytest.raises(ValueError, match="Mount point must be an absolute path"):
            aws_manager._validate_volume_spec(invalid_volume_relative, 0, 0)

        # Test dangerous system path
        invalid_volume_system = {
            "size": 50,
            "mount_point": "/etc",  # Reserved system directory
        }

        with pytest.raises(ValueError, match="is a reserved system directory"):
            aws_manager._validate_volume_spec(invalid_volume_system, 0, 0)

    def test_validate_volume_spec_invalid_filesystem(self, aws_manager):
        """Test volume specification validation with invalid filesystem."""
        invalid_volume = {
            "size": 50,
            "mount_point": "/data",
            "filesystem": "invalid_fs",  # Not supported
        }

        with pytest.raises(ValueError, match="Unsupported filesystem"):
            aws_manager._validate_volume_spec(invalid_volume, 0, 0)

    def test_generate_volume_mount_script_no_volumes(self, aws_manager):
        """Test mount script generation with no volumes."""
        instance_spec = {"name": "test-instance"}

        script = aws_manager._generate_volume_mount_script(instance_spec)
        assert script == ""

    def test_generate_volume_mount_script_no_mount_points(self, aws_manager):
        """Test mount script generation with volumes but no mount points."""
        instance_spec = {
            "name": "test-instance",
            "volumes": [
                {
                    "size": 50,
                    "type": "gp3",
                    "device": "/dev/sdf",
                    # No mount_point specified
                }
            ],
        }

        script = aws_manager._generate_volume_mount_script(instance_spec)
        assert script == ""

    def test_generate_volume_mount_script_with_mount_points(self, aws_manager):
        """Test mount script generation with volumes having mount points."""
        instance_spec = {
            "name": "test-instance",
            "volumes": [
                {
                    "size": 50,
                    "type": "gp3",
                    "device": "/dev/sdf",
                    "mount_point": "/data",
                    "filesystem": "ext4",
                    "mount_options": "defaults,noatime",
                },
                {
                    "size": 100,
                    "type": "gp3",
                    "device": "/dev/sdg",
                    "mount_point": "/logs",
                    "filesystem": "xfs",
                },
            ],
        }

        script = aws_manager._generate_volume_mount_script(instance_spec)

        # Check that script contains mount commands
        assert "AUTOMATIC VOLUME MOUNTING" in script
        assert "wait_for_device" in script
        assert "is_formatted" in script
        assert "mkdir -p '/data'" in script
        assert "mkdir -p '/logs'" in script
        assert "mkfs.ext4 '/dev/sdf'" in script
        assert "mkfs.xfs '/dev/sdg'" in script
        assert "mount -o 'defaults,noatime' '/dev/sdf' '/data'" in script
        assert "mount -o 'defaults' '/dev/sdg' '/logs'" in script
        assert "/etc/fstab" in script
        assert "chown ec2-user:ec2-user" in script

    def test_prepare_user_data_with_mount_points(self, aws_manager):
        """Test user data preparation with mount points."""
        instance_spec = {
            "name": "test-instance",
            "volumes": [
                {
                    "size": 50,
                    "device": "/dev/sdf",
                    "mount_point": "/data",
                    "filesystem": "ext4",
                }
            ],
            "user_data": {"inline_script": "echo 'Hello World'"},
        }

        user_data = aws_manager._prepare_user_data(instance_spec)

        # Check that user data contains mount commands before user script
        assert "AUTOMATIC VOLUME MOUNTING" in user_data
        assert "Volume mounting completed successfully" in user_data
        assert "USER CUSTOM SCRIPT" in user_data
        assert "echo 'Hello World'" in user_data
        assert "MOUNT VERIFICATION" in user_data
        assert "mountpoint -q '/data'" in user_data

    def test_prepare_user_data_backward_compatibility(self, aws_manager):
        """Test that volumes without mount points work as before."""
        instance_spec = {
            "name": "test-instance",
            "volumes": [
                {
                    "size": 50,
                    "device": "/dev/sdf",
                    # No mount_point - should work as before
                }
            ],
            "user_data": {"inline_script": "echo 'Hello World'"},
        }

        user_data = aws_manager._prepare_user_data(instance_spec)

        # Should not contain mount commands
        assert "AUTOMATIC VOLUME MOUNTING" not in user_data
        assert "Volume mounting completed successfully" not in user_data
        # But should contain user script
        assert "USER CUSTOM SCRIPT" in user_data
        assert "echo 'Hello World'" in user_data
        # And no mount verification
        assert "MOUNT VERIFICATION" not in user_data

    def test_validate_specification_with_mount_points(self, aws_manager):
        """Test full specification validation including mount points."""
        spec_with_mount_points = {
            "instances": [
                {
                    "name": "test-instance",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "volumes": [
                        {
                            "size": 50,
                            "type": "gp3",
                            "device": "/dev/sdf",
                            "mount_point": "/data",
                            "filesystem": "ext4",
                            "mount_options": "defaults",
                        }
                    ],
                }
            ]
        }

        # Should not raise any exception
        aws_manager._validate_specification(spec_with_mount_points)


if __name__ == "__main__":
    pytest.main([__file__])

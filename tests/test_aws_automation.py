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
            ]
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
            ]
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
                    "user_data": {
                        "script_path": "examples/python_web_server.sh"
                    }
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
                    "user_data": {
                        "inline_script": "#!/bin/bash\nyum update -y\n"
                    }
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
                        "inline_script": "#!/bin/bash\necho 'test'"
                    }
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            with pytest.raises(ValueError, match="Cannot specify both script_path and inline_script"):
                manager._validate_specification(spec)

    def test_user_data_empty_fails(self):
        """Test that empty user data fails validation."""
        spec = {
            "instances": [
                {
                    "name": "user-data-empty-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "user_data": {}
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            with pytest.raises(ValueError, match="user_data must contain either script_path or inline_script"):
                manager._validate_specification(spec)

    def test_user_data_invalid_type_fails(self):
        """Test that user data with wrong type fails validation."""
        spec = {
            "instances": [
                {
                    "name": "user-data-type-test",
                    "instance_type": "t3.micro",
                    "ami_id": "ami-12345678",
                    "user_data": "this should be an object, not a string"
                }
            ]
        }

        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager()
            with pytest.raises(ValueError, match="user_data must be an object"):
                manager._validate_specification(spec)


class TestUserDataPrepation:
    """Test cases for user data script preparation."""

    @pytest.fixture
    def aws_manager(self):
        """Create an AWSResourceManager instance with mocked AWS clients."""
        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager(region="us-east-1")
            return manager

    def test_prepare_user_data_no_user_data(self, aws_manager):
        """Test user data preparation when no user data is specified."""
        instance_spec = {
            "name": "test-instance",
            "instance_type": "t3.micro",
            "ami_id": "ami-12345678"
        }
        
        result = aws_manager._prepare_user_data(instance_spec)
        assert result == ""

    @patch("builtins.open")
    def test_prepare_user_data_from_file(self, mock_open, aws_manager):
        """Test user data preparation from script file."""
        instance_spec = {
            "name": "test-instance",
            "instance_type": "t3.micro", 
            "ami_id": "ami-12345678",
            "user_data": {
                "script_path": "test_script.sh"
            }
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
            "user_data": {
                "inline_script": "#!/bin/bash\necho 'inline test'"
            }
        }
        
        result = aws_manager._prepare_user_data(instance_spec)
        
        assert "#!/bin/bash" in result
        assert "inline test" in result
        assert "User Data Script Execution Started" in result
        assert instance_spec["name"] in result


if __name__ == "__main__":
    pytest.main([__file__])

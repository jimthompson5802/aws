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
        with patch("boto3.client"), patch("boto3.resource"):
            manager = AWSResourceManager(region="us-east-1")
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


if __name__ == "__main__":
    pytest.main([__file__])

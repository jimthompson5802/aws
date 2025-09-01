#!/usr/bin/env python3
"""
Test script for the new resource listing functionality.
This tests the logic without requiring AWS credentials.
"""

import unittest
from unittest.mock import patch, Mock
from datetime import datetime

# Import the AWSResourceManager class
from script import AWSResourceManager


class TestResourceListing(unittest.TestCase):
    """Test the new resource listing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("boto3.Session"):
            self.manager = AWSResourceManager(region="us-east-1")

    def test_list_attached_volumes(self):
        """Test list_attached_volumes method."""
        # Mock EC2 client responses - this needs to simulate multiple describe_volumes calls
        mock_ec2_client = Mock()
        self.manager.ec2_client = mock_ec2_client

        mock_ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "BlockDeviceMappings": [
                                {
                                    "DeviceName": "/dev/sda1",
                                    "Ebs": {"VolumeId": "vol-1234567890abcdef0"},
                                },
                                {
                                    "DeviceName": "/dev/sdf",
                                    "Ebs": {"VolumeId": "vol-0987654321fedcba0"},
                                },
                            ],
                        }
                    ]
                }
            ]
        }

        # Mock describe_volumes to return different responses for different volume IDs
        def mock_describe_volumes(VolumeIds):
            if VolumeIds[0] == "vol-1234567890abcdef0":
                return {
                    "Volumes": [
                        {
                            "VolumeId": "vol-1234567890abcdef0",
                            "Size": 30,
                            "VolumeType": "gp3",
                            "State": "in-use",
                            "Encrypted": True,
                            "Iops": 3000,
                            "Throughput": 125,
                            "CreateTime": datetime(2025, 9, 1, 10, 0, 0),
                        }
                    ]
                }
            elif VolumeIds[0] == "vol-0987654321fedcba0":
                return {
                    "Volumes": [
                        {
                            "VolumeId": "vol-0987654321fedcba0",
                            "Size": 100,
                            "VolumeType": "gp2",
                            "State": "in-use",
                            "Encrypted": False,
                            "Iops": 300,
                            "CreateTime": datetime(2025, 9, 1, 11, 0, 0),
                        }
                    ]
                }

        mock_ec2_client.describe_volumes.side_effect = mock_describe_volumes

        # Test the method
        result = self.manager.list_attached_volumes("test-instance")

        # Verify the result
        self.assertEqual(len(result), 2)
        volume1 = result[0]
        self.assertEqual(volume1["volume_id"], "vol-1234567890abcdef0")
        self.assertEqual(volume1["device"], "/dev/sda1")
        self.assertEqual(volume1["size"], 30)
        self.assertEqual(volume1["volume_type"], "gp3")
        self.assertEqual(volume1["state"], "in-use")
        self.assertEqual(volume1["encrypted"], True)
        self.assertEqual(volume1["iops"], 3000)
        self.assertEqual(volume1["throughput"], 125)
        self.assertEqual(volume1["instance_name"], "test-instance")

        volume2 = result[1]
        self.assertEqual(volume2["volume_id"], "vol-0987654321fedcba0")
        self.assertEqual(volume2["device"], "/dev/sdf")
        self.assertEqual(volume2["size"], 100)
        self.assertEqual(volume2["volume_type"], "gp2")

    def test_list_all_volumes(self):
        """Test list_all_volumes method."""
        # Mock EC2 client response
        mock_ec2_client = Mock()
        self.manager.ec2_client = mock_ec2_client

        mock_ec2_client.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-1234567890abcdef0",
                    "Size": 30,
                    "VolumeType": "gp3",
                    "State": "in-use",
                    "Encrypted": True,
                    "Iops": 3000,
                    "Throughput": 125,
                    "CreateTime": datetime(2025, 9, 1, 10, 0, 0),
                    "Attachments": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "Device": "/dev/sda1",
                            "State": "attached",
                        }
                    ],
                },
                {
                    "VolumeId": "vol-0987654321fedcba0",
                    "Size": 100,
                    "VolumeType": "gp2",
                    "State": "available",
                    "Encrypted": False,
                    "Iops": 300,
                    "CreateTime": datetime(2025, 9, 1, 11, 0, 0),
                    "Attachments": [],
                },
            ]
        }

        mock_ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        # Test the method
        result = self.manager.list_all_volumes()

        # Verify the result
        self.assertEqual(len(result), 2)

        # Check attached volume
        attached_volume = result[0]
        self.assertEqual(attached_volume["volume_id"], "vol-1234567890abcdef0")
        self.assertEqual(attached_volume["attached_instance"], "i-1234567890abcdef0")
        self.assertEqual(attached_volume["attached_instance_name"], "test-instance")
        self.assertEqual(attached_volume["device"], "/dev/sda1")

        # Check available volume
        available_volume = result[1]
        self.assertEqual(available_volume["volume_id"], "vol-0987654321fedcba0")
        self.assertEqual(available_volume["attached_instance"], "N/A")
        self.assertEqual(available_volume["attached_instance_name"], "N/A")
        self.assertEqual(available_volume["device"], "N/A")

    def test_list_all_snapshots(self):
        """Test list_all_snapshots method."""
        # Mock EC2 client response
        mock_ec2_client = Mock()
        self.manager.ec2_client = mock_ec2_client

        mock_ec2_client.describe_snapshots.return_value = {
            "Snapshots": [
                {
                    "SnapshotId": "snap-1234567890abcdef0",
                    "Description": "Test snapshot",
                    "VolumeId": "vol-1234567890abcdef0",
                    "VolumeSize": 30,
                    "State": "completed",
                    "Progress": "100%",
                    "StartTime": datetime(2025, 9, 1, 12, 0, 0),
                    "Encrypted": True,
                    "Tags": [{"Key": "Name", "Value": "test-snapshot"}],
                },
                {
                    "SnapshotId": "snap-0987654321fedcba0",
                    "Description": "Another snapshot",
                    "VolumeId": "vol-0987654321fedcba0",
                    "VolumeSize": 100,
                    "State": "pending",
                    "Progress": "50%",
                    "StartTime": datetime(2025, 9, 1, 13, 0, 0),
                    "Encrypted": False,
                    "Tags": [],
                },
            ]
        }

        # Test the method
        result = self.manager.list_all_snapshots()

        # Verify the result
        self.assertEqual(len(result), 2)

        # Check first snapshot (should be sorted by start time, newest first)
        snapshot1 = result[0]
        self.assertEqual(snapshot1["snapshot_id"], "snap-0987654321fedcba0")
        self.assertEqual(snapshot1["name"], "N/A")
        self.assertEqual(snapshot1["progress"], "50%")

        # Check second snapshot
        snapshot2 = result[1]
        self.assertEqual(snapshot2["snapshot_id"], "snap-1234567890abcdef0")
        self.assertEqual(snapshot2["name"], "test-snapshot")
        self.assertEqual(snapshot2["progress"], "100%")


if __name__ == "__main__":
    unittest.main()

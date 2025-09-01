# Copilot Instructions

## Project Overview

This repository automates the provisioning and management of AWS EC2 instances and EBS volumes using Python, YAML specifications, and user data scripts. It supports AWS authentication via environment variables, profiles, and IAM roles. User data scripts can be provided as files or inline YAML.

## Coding Guidelines

- Follow [PEP 8](https://peps.python.org/pep-0008/) for Python code style.
- Use type annotations for all function signatures.
- Prefer logging over print statements; use the provided logger.
- All AWS interactions must use `boto3.Session` (with optional profile support).
- Validate YAML input thoroughly and provide clear error messages.
- Ensure idempotency: never create duplicate resources.
- Implement robust error handling and rollback for partial failures.
- All new features must include corresponding unit tests in `tests/`.

## Documentation

- All public functions and classes must have docstrings.
- Update `README.md` and example YAML files for any new features or changes.
- Document new user data scripts in `examples/README.md`.
- after implementing a new feature, update the `changes/CHANGELOG.md` file with a summary of changes.

## Security

- Never hardcode AWS credentials or secrets.
- Support all standard AWS credential methods (env vars, profiles, IAM roles).
- Sanitize logs to avoid leaking sensitive information.

## Pull Requests

- Include a summary of changes and testing results.
- Reference related issues or requirements from the PRD or implementation summary.
- Ensure all tests pass before submitting.

## Examples

- See `examples/` for user data scripts.
- See `example_spec.yaml` and `example_with_profile.yaml` for YAML input formats.

## Testing

- Activate the virtual environment for testing `source venv/bin/activate`
- Add/modify tests in `tests/test_aws_automation.py`.
- Use mock AWS services for unit tests (e.g., `moto` library).

## Profile Support

- All AWS operations must support the `--profile` CLI argument and YAML `profile` field.
- Default to environment variables or the default profile if none is specified.

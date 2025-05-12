import os
import sys
import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE_NAME = os.getenv("TABLE_NAME", "Demeter_Users")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "us-east-1_xNeiWSpsg")

if not USER_POOL_ID:
    raise RuntimeError("Environment variable COGNITO_USER_POOL_ID is required or must default")

# Provide fallback values required by the pool schema and password policy
DEFAULT_ADDRESS = "Unknown"
DEFAULT_PASSWORD = "Password1234@"  

# AWS clients/resources
session = boto3.Session(region_name=AWS_REGION)
dynamodb = session.resource("dynamodb")
cognito = session.client("cognito-idp")

# ---- Validate that the table exists -----------------
try:
    dynamodb.meta.client.describe_table(TableName=TABLE_NAME)
except dynamodb.meta.client.exceptions.ResourceNotFoundException:
    logger.error("DynamoDB table '%s' not found in region '%s'. "
                 "Double‑check the TABLE_NAME env var or create the table.",
                 TABLE_NAME, AWS_REGION)
    sys.exit(1)

# Obtain the table resource *after* the existence check
table = dynamodb.Table(TABLE_NAME)
# -----------------------------------------------------------------------------

def _scan_table():
    """Yield every item in the DynamoDB table (auto‑paginated)."""
    try:
        response = table.scan()
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        logger.error("DynamoDB table '%s' disappeared or is inaccessible.", TABLE_NAME)
        return
    yield from response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        yield from response.get("Items", [])


def _choose_address(item):
    """Return the best available address‑style field or the default."""
    return (
        item.get("location")
        or item.get("locationText")
        or item.get("businessAddress")
        or DEFAULT_ADDRESS
    )


def _build_attributes(item):
    """Convert a DynamoDB record to a list of Cognito attribute dicts."""
    attrs = []
    if email := item.get("email"):
        attrs.extend([
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ])
    if name := item.get("name"):
        attrs.append({"Name": "name", "Value": name})

    attrs.append({"Name": "address", "Value": _choose_address(item)})

    if role := item.get("role"):
        attrs.append({"Name": "custom:role", "Value": role})
    return attrs


def sync_user(item):
    """Create or update a Cognito user from a DynamoDB item."""
    raw_email = (item.get("email") or "").strip()
    if not raw_email:
        logger.warning("Skipping item without email: %s", item.get("id"))
        return

    username = raw_email.lower() 
    attributes = _build_attributes(item)

    try:
        cognito.admin_get_user(UserPoolId=USER_POOL_ID, Username=username)
        cognito.admin_update_user_attributes(
            UserPoolId=USER_POOL_ID,
            Username=username,
            UserAttributes=attributes,
        )
        logger.info("Updated Cognito user %s", username)
    except cognito.exceptions.UserNotFoundException:
        # User not found – attempt to create.
        try:
            cognito.admin_create_user(
                UserPoolId=USER_POOL_ID,
                Username=username,
                UserAttributes=attributes,
                TemporaryPassword=DEFAULT_PASSWORD,
                MessageAction="SUPPRESS",  
            )
            cognito.admin_set_user_password(
                UserPoolId=USER_POOL_ID,
                Username=username,
                Password=DEFAULT_PASSWORD,
                Permanent=True,
            )
            logger.info("Created Cognito user %s with default password", username)
        except cognito.exceptions.UsernameExistsException:
            logger.info("User %s already exists (case‑insensitive match). Updating attributes instead.", username)
            cognito.admin_update_user_attributes(
                UserPoolId=USER_POOL_ID,
                Username=username,
                UserAttributes=attributes,
            )
        except cognito.exceptions.InvalidParameterException as exc:
            logger.error("Failed to create user %s – %s", username, exc)
    except (ClientError, BotoCoreError) as exc:
        logger.error("Failed to sync user %s: %s", username, exc)


def handler(event=None, context=None):
    """Lambda entry point or CLI main."""
    logger.info("Starting user sync: table=%s pool=%s region=%s", TABLE_NAME, USER_POOL_ID, AWS_REGION)
    for item in _scan_table():
        sync_user(item)
    logger.info("User sync complete.")


if __name__ == "__main__":
    handler()
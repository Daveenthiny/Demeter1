import boto3
import logging
import os
import sys
from botocore.exceptions import ClientError, WaiterError

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure AWS settings via environment variables or defaults
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
AWS_PROFILE = os.environ.get('AWS_PROFILE', None)  
TABLE_PREFIX = "Demeter_"  

# --- Constants for Attribute Names ---
ATTR_ID = 'id'
ATTR_ROLE = 'role'
ATTR_EMAIL = 'email'
ATTR_VENDOR_ID = 'vendorId'
ATTR_CUSTOMER_ID = 'customerId'
ATTR_CATEGORY = 'category'
ATTR_CONDITION = 'condition'
ATTR_EXPIRY_DATE = 'expiryDate'
ATTR_GEOHASH = 'geohash'
ATTR_COMP_AVAIL = 'composterAvailability'
ATTR_ORDER_DATE = 'orderDate'
ATTR_COMP_ID = 'composterId'
ATTR_STATUS = 'status'
ATTR_REQ_DATE = 'requestDate'
ATTR_NAME = 'name'
ATTR_DESCRIPTION = 'description'
ATTR_PRICE = 'price'
ATTR_QUANTITY = 'quantity'
ATTR_IMAGE = 'image'
ATTR_LOCATION = 'location'
ATTR_ALERT_RADIUS = 'alertRadius'
ATTR_NOTIFICATIONS = 'notifications'
ATTR_CAPACITY = 'capacity'
ATTR_ACCEPTED_TYPES = 'acceptedTypes'
ATTR_ITEMS = 'items'
ATTR_VENDOR_NAME = 'vendorName'
ATTR_ITEM_ID = 'itemId'
ATTR_ITEM_PRICE = 'itemPrice'
ATTR_ITEM_QUANTITY = 'itemQuantity'
ATTR_TOTAL = 'total'

# --- Default Billing & Capacity ---
DEFAULT_BILLING_MODE = 'PAY_PER_REQUEST'
DEFAULT_READ_CAPACITY = 5
DEFAULT_WRITE_CAPACITY = 5

# --- Boto3 Client Initialization ---
try:
    session_args = {'region_name': AWS_REGION}
    if AWS_PROFILE:
        session_args['profile_name'] = AWS_PROFILE
        logging.info(f"Using AWS Profile: {AWS_PROFILE}")
    else:
        logging.info("Using default AWS credentials chain (environment/instance profile/etc.)")

    session = boto3.Session(**session_args)
    dynamodb = session.client('dynamodb')
    logging.info(f"DynamoDB client configured for region: {AWS_REGION}")

except Exception as e:
    logging.error(f"Failed to create Boto3 session/client in region {AWS_REGION}: {e}", exc_info=True)
    sys.exit(1)

# --- Utility Functions ---
def wait_for_table(dynamodb, table_name):
    waiter = dynamodb.get_waiter('table_exists')
    try:
        waiter.wait(
            TableName=table_name,
            WaiterConfig={'Delay': 5, 'MaxAttempts': 20}
        )
        logging.info(f"Table {table_name} is now active.")
    except WaiterError as e:
        logging.error(f"Failed to wait for table {table_name} to become active: {e}")
        raise

# --- Table Creation Function ---
def create_table(
    table_name,
    key_schema,
    attribute_definitions,
    global_secondary_indexes=None,
    billing_mode=DEFAULT_BILLING_MODE,
    read_capacity=DEFAULT_READ_CAPACITY,
    write_capacity=DEFAULT_WRITE_CAPACITY):
    """
    Creates a DynamoDB table with specified schema, GSIs, and billing mode.
    """
    full_table_name = f"{TABLE_PREFIX}{table_name}"
    logging.info(f"Attempting to create table: {full_table_name} with BillingMode: {billing_mode}...")

    params = {
        'TableName': full_table_name,
        'KeySchema': key_schema,
        'AttributeDefinitions': attribute_definitions,
        'BillingMode': billing_mode
    }

    if billing_mode == 'PROVISIONED':
        params['ProvisionedThroughput'] = {
            'ReadCapacityUnits': read_capacity,
            'WriteCapacityUnits': write_capacity
        }
        if global_secondary_indexes:
            for gsi in global_secondary_indexes:
                if 'ProvisionedThroughput' not in gsi:
                    gsi['ProvisionedThroughput'] = {
                        'ReadCapacityUnits': read_capacity,
                        'WriteCapacityUnits': write_capacity
                    }
    elif global_secondary_indexes:
        for gsi in global_secondary_indexes:
            if 'ProvisionedThroughput' in gsi:
                del gsi['ProvisionedThroughput']

    if global_secondary_indexes:
        params['GlobalSecondaryIndexes'] = global_secondary_indexes

    try:
        table_description = dynamodb.create_table(**params)
        logging.info(f"Waiting for table {full_table_name} to become active...")
        wait_for_table(dynamodb, full_table_name)
        logging.info(f"Table {full_table_name} created successfully and is active.")
        return table_description
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        if error_code == 'ResourceInUseException':
            logging.warning(f"Table {full_table_name} already exists.")
        else:
            logging.error(f"Error creating table {full_table_name}: {e.response['Error']['Message']}")
    except Exception as e:
        logging.error(f"An unexpected error occurred creating table {full_table_name}: {e}", exc_info=True)

    return None

# --- Table Definitions ---
def get_table_definitions():
    return {
        'Users': {
            'key_schema': [{'AttributeName': ATTR_ID, 'KeyType': 'HASH'}],
            'attribute_definitions': [
                {'AttributeName': ATTR_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_ROLE, 'AttributeType': 'S'},
                {'AttributeName': ATTR_EMAIL, 'AttributeType': 'S'}
            ],
            'global_secondary_indexes': [
                {
                    'IndexName': 'RoleIndex',
                    'KeySchema': [{'AttributeName': ATTR_ROLE, 'KeyType': 'HASH'}],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'EmailIndex',
                    'KeySchema': [{'AttributeName': ATTR_EMAIL, 'KeyType': 'HASH'}],
                    'Projection': {'ProjectionType': 'INCLUDE', 'NonKeyAttributes': [ATTR_ID, ATTR_ROLE]}
                }
            ]
        },
        'FoodItems': {
            'key_schema': [{'AttributeName': ATTR_ID, 'KeyType': 'HASH'}],
            'attribute_definitions': [
                {'AttributeName': ATTR_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_VENDOR_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_CATEGORY, 'AttributeType': 'S'},
                {'AttributeName': ATTR_EXPIRY_DATE, 'AttributeType': 'S'},
                {'AttributeName': ATTR_GEOHASH, 'AttributeType': 'S'},
                {'AttributeName': ATTR_COMP_AVAIL, 'AttributeType': 'S'}
            ],
            'global_secondary_indexes': [
                {
                    'IndexName': 'VendorIndex',
                    'KeySchema': [{'AttributeName': ATTR_VENDOR_ID, 'KeyType': 'HASH'}],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'CategoryExpiryIndex',
                    'KeySchema': [
                        {'AttributeName': ATTR_CATEGORY, 'KeyType': 'HASH'},
                        {'AttributeName': ATTR_EXPIRY_DATE, 'KeyType': 'RANGE'}
                    ],
                    'Projection': {
                        'ProjectionType': 'INCLUDE',
                        'NonKeyAttributes': [ATTR_ID, ATTR_NAME, ATTR_PRICE, ATTR_VENDOR_ID, ATTR_LOCATION, ATTR_CONDITION, ATTR_QUANTITY, ATTR_EXPIRY_DATE, ATTR_IMAGE, ATTR_COMP_AVAIL]
                    }
                },
                {
                    'IndexName': 'GeoIndex',
                    'KeySchema': [{'AttributeName': ATTR_GEOHASH, 'KeyType': 'HASH'}],
                    'Projection': {
                        'ProjectionType': 'INCLUDE',
                        'NonKeyAttributes': [ATTR_ID, ATTR_NAME, ATTR_PRICE, ATTR_LOCATION, ATTR_QUANTITY]
                    }
                },
                {
                    'IndexName': 'ComposterAvailabilityIndex',
                    'KeySchema': [{'AttributeName': ATTR_COMP_AVAIL, 'KeyType': 'HASH'}],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ]
        },
        'Orders': {
            'key_schema': [{'AttributeName': ATTR_ID, 'KeyType': 'HASH'}],
            'attribute_definitions': [
                {'AttributeName': ATTR_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_CUSTOMER_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_VENDOR_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_ORDER_DATE, 'AttributeType': 'S'}
            ],
            'global_secondary_indexes': [
                {
                    'IndexName': 'CustomerOrderIndex',
                    'KeySchema': [
                        {'AttributeName': ATTR_CUSTOMER_ID, 'KeyType': 'HASH'},
                        {'AttributeName': ATTR_ORDER_DATE, 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'VendorOrderIndex',
                    'KeySchema': [
                        {'AttributeName': ATTR_VENDOR_ID, 'KeyType': 'HASH'},
                        {'AttributeName': ATTR_ORDER_DATE, 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ]
        },
        'OrderItems': {
            'key_schema': [
                {'AttributeName': ATTR_ID, 'KeyType': 'HASH'}, # Order ID
                {'AttributeName': ATTR_ITEM_ID, 'KeyType': 'RANGE'} # Food Item ID within the order
            ],
            'attribute_definitions': [
                {'AttributeName': ATTR_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_ITEM_ID, 'AttributeType': 'S'}
            ]
        },
        'PickupRequests': {
            'key_schema': [{'AttributeName': ATTR_ID, 'KeyType': 'HASH'}], # Unique Request ID
            'attribute_definitions': [
                {'AttributeName': ATTR_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_COMP_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_VENDOR_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_ITEM_ID, 'AttributeType': 'S'},
                {'AttributeName': ATTR_STATUS, 'AttributeType': 'S'}
            ],
            'global_secondary_indexes': [
                {
                    'IndexName': 'ComposterRequestIndex',
                    'KeySchema': [
                        {'AttributeName': ATTR_COMP_ID, 'KeyType': 'HASH'},
                        {'AttributeName': ATTR_STATUS, 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'VendorRequestIndex',
                    'KeySchema': [
                        {'AttributeName': ATTR_VENDOR_ID, 'KeyType': 'HASH'},
                        {'AttributeName': ATTR_STATUS, 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'ItemRequestIndex',
                    'KeySchema': [{'AttributeName': ATTR_ITEM_ID, 'KeyType': 'HASH'}],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ]
        }
    }

# --- Main Execution Block ---
if __name__ == "__main__":
    logging.info("Starting DynamoDB table creation process...")
    table_definitions = get_table_definitions()

    for table_name, table_config in table_definitions.items():
        create_table(
            table_name=table_name,
            key_schema=table_config['key_schema'],
            attribute_definitions=table_config['attribute_definitions'],
            global_secondary_indexes=table_config.get('global_secondary_indexes')
        )

    logging.info("DynamoDB table creation process finished.")
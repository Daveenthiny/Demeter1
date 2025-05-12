import boto3
import uuid
from decimal import Decimal  # Use Decimal for currency/precise numbers
import datetime
import random  # For generating some mock data variability
import logging
import os
import sys
from botocore.exceptions import ClientError

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure AWS settings via environment variables or defaults
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
AWS_PROFILE = os.environ.get('AWS_PROFILE', None)  # Use default profile if not set
TABLE_PREFIX = os.environ.get('TABLE_PREFIX', 'Demeter_')  # Match prefix used in creation script
DRY_RUN = os.environ.get('DRY_RUN', 'false').lower() == 'true'

# --- Constants for Attribute Names (match creation script) ---
ATTR_ID = 'id'
ATTR_ROLE = 'role'
ATTR_EMAIL = 'email'
ATTR_NAME = 'name'
ATTR_LOCATION = 'location'
ATTR_LAT = 'lat'
ATTR_LON = 'lon'
ATTR_GEOHASH = 'geohash'
ATTR_VENDOR_ID = 'vendorId'
ATTR_CUSTOMER_ID = 'customerId'
ATTR_CATEGORY = 'category'
ATTR_CONDITION = 'condition'
ATTR_EXPIRY_DATE = 'expiryDate'
ATTR_COMP_AVAIL = 'composterAvailability'
ATTR_ORDER_DATE = 'orderDate'
ATTR_PRICE = 'price'
ATTR_QUANTITY = 'quantity'
ATTR_STATUS = 'status'
ATTR_CREATED_AT = 'createdAt'
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
ATTR_REQ_DATE = 'requestDate'
ATTR_COMP_ID = 'composterId'

# --- Boto3 Resource Initialization ---
try:
    session_args = {'region_name': AWS_REGION}
    if AWS_PROFILE:
        session_args['profile_name'] = AWS_PROFILE
        logging.info(f"Using AWS Profile: {AWS_PROFILE}")
    else:
        logging.info("Using default AWS credentials chain (environment/instance profile/etc.)")

    session = boto3.Session(**session_args)
    dynamodb = session.resource('dynamodb')
    logging.info(f"DynamoDB resource client configured for region: {AWS_REGION}")

except Exception as e:
    logging.error(f"Failed to create Boto3 session/resource in region {AWS_REGION}: {e}", exc_info=True)
    sys.exit(1)

# --- Helper Functions ---
def float_to_decimal(f):
    """Converts a float to a Decimal for DynamoDB Number compatibility."""
    return Decimal(str(f))

def get_iso_utc_now():
    """Returns the current UTC time as an ISO 8601 string with Z."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def retry_batch_write(batch_writer, items, retries=3):
    """Retries batch writes to DynamoDB in case of transient errors."""
    for attempt in range(retries):
        try:
            for item in items:
                batch_writer.put_item(Item=item)
            return True
        except ClientError as e:
            if attempt < retries - 1:
                logging.warning(f"Retrying batch write due to error: {e.response['Error']['Message']}")
            else:
                logging.error(f"Failed to write batch after {retries} attempts: {e.response['Error']['Message']}")
                raise

def validate_user_data(user_data):
    """Validates user data before adding it to DynamoDB."""
    required_fields = [ATTR_EMAIL, ATTR_NAME, ATTR_ROLE]
    for field in required_fields:
        if field not in user_data:
            raise ValueError(f"Missing required field: {field}")

# --- Data Population Functions ---
def populate_users():
    """Populates the Users table with sample data and returns generated IDs."""
    table = dynamodb.Table(f"{TABLE_PREFIX}Users")
    logging.info(f"Populating table: {table.name}...")
    generated_user_ids = {}
    users_to_create = []
    now_iso = get_iso_utc_now()

    user_defs = [
        {'logical_id': 'customer1', ATTR_EMAIL: 'customer@test.com', ATTR_NAME: 'Test Customer', ATTR_ROLE: 'Customer', ATTR_LOCATION: 'Catonsville, MD', ATTR_ALERT_RADIUS: 5, ATTR_NOTIFICATIONS: True},
        {'logical_id': 'vendor1', ATTR_EMAIL: 'vendor@test.com', ATTR_NAME: 'Local Farm Stand', ATTR_ROLE: 'Vendor', ATTR_LOCATION: '123 Farm Rd, Catonsville, MD'},
        {'logical_id': 'composter1', ATTR_EMAIL: 'composter@test.com', ATTR_NAME: 'Community Compost', ATTR_ROLE: 'Composter', ATTR_LOCATION: '456 Green St, Catonsville, MD', ATTR_CAPACITY: '100 lbs/week', ATTR_ACCEPTED_TYPES: 'Fruits, Vegetables, Coffee Grounds'},
    ]

    for user_def in user_defs:
        try:
            validate_user_data(user_def)
            user_id = str(uuid.uuid4())
            logical_id_key = f"{user_def['logical_id']}_id"
            generated_user_ids[logical_id_key] = user_id

            user_item = {
                ATTR_ID: user_id,
                ATTR_CREATED_AT: now_iso,
                **{k: v for k, v in user_def.items() if k != 'logical_id'}
            }
            users_to_create.append(user_item)
        except ValueError as e:
            logging.error(f"Validation error for user: {user_def}. Error: {e}")

    if DRY_RUN:
        logging.info(f"Dry run: {len(users_to_create)} users would be added.")
        return generated_user_ids

    try:
        with table.batch_writer() as batch:
            retry_batch_write(batch, users_to_create)
        logging.info(f"{table.name} populated successfully.")
        return generated_user_ids
    except Exception as e:
        logging.error(f"Failed to populate {table.name}: {e}", exc_info=True)
        return {}

def populate_food_items(user_ids):
    """Populates the FoodItems table using vendor IDs and returns created items."""
    table = dynamodb.Table(f"{TABLE_PREFIX}FoodItems")
    logging.info(f"Populating table: {table.name}...")
    now_iso = get_iso_utc_now()
    created_items = []

    vendor1_id = user_ids.get('vendor1_id')
    if not vendor1_id:
        logging.error("Vendor IDs not found. Cannot populate FoodItems.")
        return []

    vendor1_location = '123 Farm Rd, Catonsville, MD'
    vendor1_name = 'Local Farm Stand'

    item_defs = [
        {ATTR_VENDOR_ID: vendor1_id, ATTR_VENDOR_NAME: vendor1_name, ATTR_NAME: 'Slightly Bruised Apples', 'description': 'Perfectly good for eating or baking...', ATTR_CATEGORY: 'produce', ATTR_CONDITION: 'imperfect', ATTR_PRICE: float_to_decimal(2.99), 'originalPrice': float_to_decimal(5.99), 'days_until_expiry': 5, 'image': 'placeholder-images/apples.jpg', ATTR_COMP_AVAIL: True, ATTR_LOCATION: vendor1_location, ATTR_QUANTITY: 10},
        {ATTR_VENDOR_ID: vendor1_id, ATTR_VENDOR_NAME: vendor1_name, ATTR_NAME: 'Overripe Bananas', 'description': 'Great for smoothies or banana bread!', ATTR_CATEGORY: 'produce', ATTR_CONDITION: 'overripe', ATTR_PRICE: float_to_decimal(1.00), 'originalPrice': float_to_decimal(3.00), 'days_until_expiry': 2, 'image': 'placeholder-images/bananas.jpg', ATTR_COMP_AVAIL: True, ATTR_LOCATION: vendor1_location, ATTR_QUANTITY: 15},
        {ATTR_VENDOR_ID: vendor1_id, ATTR_VENDOR_NAME: vendor1_name, ATTR_NAME: 'Day-Old Bread', 'description': 'Still delicious, perfect for toast or croutons.', ATTR_CATEGORY: 'bakery', ATTR_CONDITION: 'day-old', ATTR_PRICE: float_to_decimal(2.50), 'originalPrice': float_to_decimal(4.00), 'days_until_expiry': 3, 'image': 'placeholder-images/bread.jpg', ATTR_COMP_AVAIL: False, ATTR_LOCATION: vendor1_location, ATTR_QUANTITY: 5},
    ]

    items_to_create = []
    for item_def in item_defs:
        item_id = 'item-' + str(uuid.uuid4())
        expiry_date = (datetime.date.today() + datetime.timedelta(days=item_def['days_until_expiry'])).isoformat()

        item = {
            ATTR_ID: item_id,
            ATTR_VENDOR_ID: item_def[ATTR_VENDOR_ID],
            ATTR_VENDOR_NAME: item_def[ATTR_VENDOR_NAME],
            ATTR_NAME: item_def[ATTR_NAME],
            'description': item_def.get('description'),
            ATTR_CATEGORY: item_def[ATTR_CATEGORY],
            ATTR_CONDITION: item_def[ATTR_CONDITION],
            ATTR_PRICE: item_def[ATTR_PRICE],
            'originalPrice': item_def.get('originalPrice'),
            ATTR_QUANTITY: item_def[ATTR_QUANTITY],
            ATTR_EXPIRY_DATE: expiry_date,
            'image': item_def.get('image'),
            ATTR_LOCATION: item_def[ATTR_LOCATION],
            ATTR_CREATED_AT: now_iso
        }

        item[ATTR_COMP_AVAIL] = "1" if item_def.get(ATTR_COMP_AVAIL) else "0"

        items_to_create.append(item)
        created_items.append(item)

    if DRY_RUN:
        logging.info(f"Dry run: {len(items_to_create)} food items would be added.")
        return created_items

    try:
        with table.batch_writer() as batch:
            retry_batch_write(batch, items_to_create)
        logging.info(f"{table.name} populated successfully.")
        return created_items
    except Exception as e:
        logging.error(f"Failed to populate {table.name}: {e}", exc_info=True)
        return []

def populate_orders(user_ids, created_items):
    """Populates the Orders table using customer/vendor IDs."""
    table = dynamodb.Table(f"{TABLE_PREFIX}Orders")
    logging.info(f"Populating table: {table.name}...")
    now_iso = get_iso_utc_now()

    customer1_id = user_ids.get('customer1_id')
    vendor1_id = user_ids.get('vendor1_id')

    if not customer1_id or not vendor1_id:
        logging.error("Customer or Vendor IDs not found. Cannot populate Orders.")
        return []

    vendor1_items = [item for item in created_items if item[ATTR_VENDOR_ID] == vendor1_id]
    if not vendor1_items:
        logging.warning("No items found from vendor1. Skipping order population.")
        return []

    order_items_data = []
    total_amount = Decimal('0.00')
    for i in range(random.randint(1, min(3, len(vendor1_items)))):
        item = random.choice(vendor1_items)
        quantity = random.randint(1, min(3, item[ATTR_QUANTITY]))
        price = item[ATTR_PRICE]
        order_items_data.append({
            ATTR_ITEM_ID: item[ATTR_ID],
            ATTR_ITEM_QUANTITY: quantity,
            ATTR_ITEM_PRICE: price
        })
        total_amount += price * Decimal(quantity)

    if not order_items_data:
        logging.warning("No order items to create.")
        return []

    orders_to_create = [
        {
            ATTR_ID: 'order-' + str(uuid.uuid4()),
            ATTR_CUSTOMER_ID: customer1_id,
            ATTR_VENDOR_ID: vendor1_id,
            ATTR_ORDER_DATE: (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=random.randint(1, 7))).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            ATTR_STATUS: random.choice(['Pending', 'Shipped', 'Delivered']),
            ATTR_TOTAL: total_amount,
            ATTR_CREATED_AT: now_iso
        },
    ]

    if DRY_RUN:
        logging.info(f"Dry run: {len(orders_to_create)} orders would be added.")
        return orders_to_create

    try:
        with table.batch_writer() as batch:
            retry_batch_write(batch, orders_to_create)
        logging.info(f"{table.name} populated successfully.")
        return orders_to_create
    except Exception as e:
        logging.error(f"Failed to populate {table.name}: {e}", exc_info=True)
        return []

def populate_order_items(orders):
    """Populates the OrderItems table using order data."""
    table = dynamodb.Table(f"{TABLE_PREFIX}OrderItems")
    logging.info(f"Populating table: {table.name}...")
    items_to_create = []

    for order in orders:
        order_id = order[ATTR_ID]
        for item in order.get('orderItems', []):
            items_to_create.append({
                ATTR_ID: order_id,
                ATTR_ITEM_ID: item[ATTR_ITEM_ID],
                ATTR_ITEM_PRICE: item[ATTR_ITEM_PRICE],
                ATTR_ITEM_QUANTITY: item[ATTR_ITEM_QUANTITY]
            })

    if DRY_RUN:
        logging.info(f"Dry run: {len(items_to_create)} order items would be added.")
        return

    try:
        with table.batch_writer() as batch:
            retry_batch_write(batch, items_to_create)
        logging.info(f"{table.name} populated successfully.")
    except Exception as e:
        logging.error(f"Failed to populate {table.name}: {e}", exc_info=True)

def populate_pickup_requests(user_ids, created_items):
    """Populates the PickupRequests table."""
    table = dynamodb.Table(f"{TABLE_PREFIX}PickupRequests")
    logging.info(f"Populating table: {table.name}...")
    now_iso = get_iso_utc_now()
    requests_to_create = []

    composter1_id = user_ids.get('composter1_id')
    vendor1_id = user_ids.get('vendor1_id')

    if not composter1_id or not vendor1_id:
        logging.error("Composter or Vendor IDs not found. Cannot populate PickupRequests.")
        return

    available_food = [item for item in created_items if item.get(ATTR_COMP_AVAIL)]
    if not available_food:
        logging.warning("No composter-available food items found.")
        return

    for item in random.sample(available_food, min(2, len(available_food))):
        request_id = 'req-' + str(uuid.uuid4())
        requests_to_create.append({
            ATTR_ID: request_id,
            ATTR_COMP_ID: composter1_id,
            ATTR_VENDOR_ID: item[ATTR_VENDOR_ID],
            ATTR_ITEM_ID: item[ATTR_ID],
            ATTR_REQ_DATE: (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=random.randint(0, 3))).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            ATTR_STATUS: random.choice(['Pending', 'Accepted', 'Rejected'])
        })

    if DRY_RUN:
        logging.info(f"Dry run: {len(requests_to_create)} pickup requests would be added.")
        return

    try:
        with table.batch_writer() as batch:
            retry_batch_write(batch, requests_to_create)
        logging.info(f"{table.name} populated successfully.")
    except Exception as e:
        logging.error(f"Failed to populate {table.name}: {e}", exc_info=True)

# --- Main Execution Block ---
if __name__ == "__main__":
    logging.info("Starting DynamoDB data population process...")

    generated_users = populate_users()
    if generated_users:
        generated_items = populate_food_items(generated_users)
        if generated_items:
            generated_orders = populate_orders(generated_users, generated_items)
            if generated_orders:
                populate_order_items(generated_orders)
            populate_pickup_requests(generated_users, generated_items)

    logging.info("\nPopulation process finished.")
    logging.info("NOTE: Dry run mode is enabled." if DRY_RUN else "NOTE: Data has been written to DynamoDB.")
import boto3
import uuid
from decimal import Decimal  # Use Decimal for currency/precise numbers
import datetime
import random  # For generating some mock data variability
import logging
import os
import sys
from botocore.exceptions import ClientError
from geopy.geocoders import Nominatim  # For generating realistic locations (requires internet)
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure AWS settings via environment variables or defaults
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
AWS_PROFILE = os.environ.get('AWS_PROFILE', None)  # Use default profile if not set
TABLE_PREFIX = os.environ.get('TABLE_PREFIX', 'Demeter_')  # Match prefix used in creation script
DRY_RUN = os.environ.get('DRY_RUN', 'false').lower() == 'true'
NUM_RECORDS = 50

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

def generate_random_location(geolocator, attempts=3):
    """Generates a random location within a reasonable range of Catonsville, MD."""
    min_lat, max_lat = 39.2, 39.4  # Latitude range around Catonsville
    min_lon, max_lon = -76.8, -76.6  # Longitude range around Catonsville
    for _ in range(attempts):
        lat = random.uniform(min_lat, max_lat)
        lon = random.uniform(min_lon, max_lon)
        try:
            location = geolocator.reverse(f"{lat}, {lon}", exactly_one=True, timeout=3)
            if location and 'Maryland' in location.address:
                return location.address, lat, lon
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logging.warning(f"Geocoding service error: {e}. Retrying...")
        except Exception as e:
            logging.error(f"Unexpected error during geocoding: {e}")
            return "Unknown Location", lat, lon
    return "Catonsville, MD (Fallback)", 39.28, -76.78

# --- Data Population Functions ---
def populate_users(num_records=NUM_RECORDS):
    """Populates the Users table with sample data and returns generated IDs."""
    table = dynamodb.Table(f"{TABLE_PREFIX}Users")
    logging.info(f"Populating table: {table.name} with {num_records} records...")
    generated_user_ids = {'customer': [], 'vendor': [], 'composter': []}
    users_to_create = []
    now_iso = get_iso_utc_now()
    geolocator = Nominatim(user_agent="demeter_data_populator")

    roles = ['Customer', 'Vendor', 'Composter']
    accepted_types_options = ['Fruits, Vegetables', 'Baked Goods', 'Dairy', 'Meat', 'Compostable Packaging']
    capacity_options = ['50 lbs/week', '100 lbs/week', '200 lbs/week', '500 lbs/week']

    for i in range(num_records):
        role = random.choice(roles)
        try:
            name = f"{role.capitalize()} {i+1}"
            email = f"{role.lower()}{i+1}@test.com"
            location_address, lat, lon = generate_random_location(geolocator)
            user_id = str(uuid.uuid4())
            generated_user_ids[role.lower()].append(user_id)

            user_item = {
                ATTR_ID: user_id,
                ATTR_CREATED_AT: now_iso,
                ATTR_ROLE: role,
                ATTR_EMAIL: email,
                ATTR_NAME: name,
                ATTR_LOCATION: location_address,
                ATTR_LAT: float_to_decimal(lat),
                ATTR_LON: float_to_decimal(lon),
            }
            if role == 'Customer':
                user_item[ATTR_ALERT_RADIUS] = random.randint(1, 10)
                user_item[ATTR_NOTIFICATIONS] = random.choice([True, False])
            elif role == 'Composter':
                user_item[ATTR_CAPACITY] = random.choice(capacity_options)
                user_item[ATTR_ACCEPTED_TYPES] = random.choice(accepted_types_options)

            users_to_create.append(user_item)
        except ValueError as e:
            logging.error(f"Validation error for user {i+1}: {e}")
        except Exception as e:
            logging.error(f"Error generating user {i+1}: {e}")

    if DRY_RUN:
        logging.info(f"Dry run: {len(users_to_create)} users would be added.")
        return generated_user_ids

    try:
        with table.batch_writer() as batch:
            retry_batch_write(batch, users_to_create)
        logging.info(f"{table.name} populated successfully with {len(users_to_create)} records.")
        return generated_user_ids
    except Exception as e:
        logging.error(f"Failed to populate {table.name}: {e}", exc_info=True)
        return {}

def populate_food_items(user_ids, num_records=NUM_RECORDS):
    """Populates the FoodItems table with sample data."""
    table = dynamodb.Table(f"{TABLE_PREFIX}FoodItems")
    logging.info(f"Populating table: {table.name} with {num_records} records...")
    now_iso = get_iso_utc_now()
    items_to_create = []
    geolocator = Nominatim(user_agent="demeter_data_populator")

    vendor_ids = user_ids.get('vendor', [])
    if not vendor_ids:
        logging.warning("No vendor IDs found. Cannot populate FoodItems.")
        return []

    categories = ['produce', 'bakery', 'dairy', 'meat', 'prepared foods']
    conditions = ['fresh', 'slightly bruised', 'overripe', 'day-old', 'frozen']

    for i in range(num_records):
        vendor_id = random.choice(vendor_ids)
        vendor_name = f"Vendor {vendor_ids.index(vendor_id) + 1}" # Simple way to get a name
        category = random.choice(categories)
        condition = random.choice(conditions)
        price = float_to_decimal(random.uniform(1.0, 15.0))
        quantity = random.randint(1, 50)
        days_until_expiry = random.randint(1, 10)
        expiry_date = (datetime.date.today() + datetime.timedelta(days=days_until_expiry)).isoformat()
        composter_availability = random.choice([0, 1]) # 0 for False, 1 for True
        name = f"{condition.capitalize()} {category.capitalize()} Item {i+1}"
        location_address, lat, lon = generate_random_location(geolocator)

        item = {
            ATTR_ID: 'item-' + str(uuid.uuid4()),
            ATTR_VENDOR_ID: vendor_id,
            ATTR_VENDOR_NAME: vendor_name,
            ATTR_NAME: name,
            ATTR_CATEGORY: category,
            ATTR_CONDITION: condition,
            ATTR_PRICE: price,
            ATTR_QUANTITY: quantity,
            ATTR_EXPIRY_DATE: expiry_date,
            ATTR_COMP_AVAIL: composter_availability,
            ATTR_LOCATION: location_address,
            ATTR_LAT: float_to_decimal(lat),
            ATTR_LON: float_to_decimal(lon),
            ATTR_CREATED_AT: now_iso
        }
        items_to_create.append(item)

    if DRY_RUN:
        logging.info(f"Dry run: {len(items_to_create)} food items would be added.")
        return items_to_create

    try:
        with table.batch_writer() as batch:
            retry_batch_write(batch, items_to_create)
        logging.info(f"{table.name} populated successfully with {len(items_to_create)} records.")
        return items_to_create
    except Exception as e:
        logging.error(f"Failed to populate {table.name}: {e}", exc_info=True)
        return []

def populate_orders(user_ids, created_items, num_records=NUM_RECORDS):
    """Populates the Orders table using customer/vendor IDs."""
    table = dynamodb.Table(f"{TABLE_PREFIX}Orders")
    logging.info(f"Populating table: {table.name} with {num_records} records...")
    now_iso = get_iso_utc_now()
    orders_to_create = []

    customer_ids = user_ids.get('customer', [])
    vendor_ids = user_ids.get('vendor', [])

    if not customer_ids or not vendor_ids:
        logging.warning("Customer or Vendor IDs not found. Cannot fully populate Orders.")
        return []

    for i in range(num_records):
        customer_id = random.choice(customer_ids)
        vendor_id = random.choice(vendor_ids)
        order_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=random.randint(0, 30))).isoformat(timespec='seconds').replace('+00:00', 'Z')
        status = random.choice(['Pending', 'Shipped', 'Delivered', 'Cancelled'])
        total_amount = Decimal('0.00')
        order_items = []

        # Add 1-5 random items to each order
        num_items = random.randint(1, 5)
        available_vendor_items = [item for item in created_items if item[ATTR_VENDOR_ID] == vendor_id]

        if available_vendor_items:
            selected_items = random.sample(available_vendor_items, min(num_items, len(available_vendor_items)))
            for item in selected_items:
                quantity = random.randint(1, min(3, item.get(ATTR_QUANTITY, 1)))
                price = item[ATTR_PRICE]
                order_items.append({
                    ATTR_ITEM_ID: item[ATTR_ID],
                    ATTR_ITEM_QUANTITY: quantity,
                    ATTR_ITEM_PRICE: price
                })
                total_amount += price * Decimal(quantity)

        order = {
            ATTR_ID: 'order-' + str(uuid.uuid4()),
            ATTR_CUSTOMER_ID: customer_id,
            ATTR_VENDOR_ID: vendor_id,
            ATTR_ORDER_DATE: order_date,
            ATTR_STATUS: status,
            ATTR_TOTAL: total_amount,
            ATTR_CREATED_AT: now_iso,
            'orderItems': order_items # Temporarily store for populating OrderItems table
        }
        orders_to_create.append(order)

    if DRY_RUN:
        logging.info(f"Dry run: {len(orders_to_create)} orders would be added.")
        return orders_to_create

    try:
        with table.batch_writer() as batch:
            retry_batch_write(batch, [
                {k: v for k, v in order.items() if k != 'orderItems'} for order in orders_to_create
            ])
        logging.info(f"{table.name} populated successfully with {len(orders_to_create)} records.")
        return orders_to_create
    except Exception as e:
        logging.error(f"Failed to populate {table.name}: {e}", exc_info=True)
        return []

def populate_order_items(orders, num_records_per_order=5): # Adjust as needed
    """Populates the OrderItems table using order data."""
    table = dynamodb.Table(f"{TABLE_PREFIX}OrderItems")
    logging.info(f"Populating table: {table.name} based on orders...")
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
        logging.info(f"{table.name} populated successfully with {len(items_to_create)} records.")
    except Exception as e:
        logging.error(f"Failed to populate {table.name}: {e}", exc_info=True)

def populate_pickup_requests(user_ids, created_items, num_records=NUM_RECORDS):
    """Populates the PickupRequests table."""
    table = dynamodb.Table(f"{TABLE_PREFIX}PickupRequests")
    logging.info(f"Populating table: {table.name} with {num_records} records...")
    now_iso = get_iso_utc_now()
    requests_to_create = []

    composter_ids = user_ids.get('composter', [])
    vendor_ids = user_ids.get('vendor', [])

    if not composter_ids or not vendor_ids:
        logging.warning("Composter or Vendor IDs not found. Cannot fully populate PickupRequests.")
        return

    available_food = [item for item in created_items if item.get(ATTR_COMP_AVAIL) == 1]

    for i in range(num_records):
        if not available_food:
            logging.warning("No composter-available food items found to create pickup requests.")
            break

        item = random.choice(available_food)
        composter_id = random.choice(composter_ids)
        vendor_id = item[ATTR_VENDOR_ID]
        request_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=random.randint(0, 14))).isoformat(timespec='seconds').replace('+00:00', 'Z')
        status = random.choice(['Pending', 'Accepted', 'Rejected', 'Completed'])

        request_id = 'req-' + str(uuid.uuid4())
        requests_to_create.append({
            ATTR_ID: request_id,
            ATTR_COMP_ID: composter_id,
            ATTR_VENDOR_ID: vendor_id,
            ATTR_ITEM_ID: item[ATTR_ID],
            ATTR_REQ_DATE: request_date,
            ATTR_STATUS: status,
            ATTR_CREATED_AT: now_iso
        })

    if DRY_RUN:
        logging.info(f"Dry run: {len(requests_to_create)} pickup requests would be added.")
        return

    try:
        with table.batch_writer() as batch:
            retry_batch_write(batch, requests_to_create)
        logging.info(f"{table.name} populated successfully with {len(requests_to_create)} records.")
    except Exception as e:
        logging.error(f"Failed to populate {table.name}: {e}", exc_info=True)

# --- Main Execution Block ---
if __name__ == "__main__":
    logging.info("Starting DynamoDB data population process with 1000 records per table (if possible)...")

    generated_users = populate_users(NUM_RECORDS)
    if generated_users:
        generated_items = populate_food_items(generated_users, NUM_RECORDS)
        if generated_items:
            generated_orders = populate_orders(generated_users, generated_items, NUM_RECORDS)
            if generated_orders:
                populate_order_items(generated_orders)
            populate_pickup_requests(generated_users, generated_items, NUM_RECORDS)

    logging.info("\nPopulation process finished.")
    logging.info("NOTE: Dry run mode is enabled." if DRY_RUN else "NOTE: Data has been written to DynamoDB.")
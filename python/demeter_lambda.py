from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from typing import Any, Dict, Optional, Set, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    force=True,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lambda env & boto3 clients
# ---------------------------------------------------------------------------
LAMBDA_ENV    = bool(os.getenv("AWS_EXECUTION_ENV"))
AWS_REGION    = os.getenv("AWS_REGION")
AWS_PROFILE   = os.getenv("AWS_PROFILE") if not LAMBDA_ENV else None
TABLE_PREFIX = "Demeter_"

session_kwargs: Dict[str, str] = {}
if AWS_REGION:
    session_kwargs["region_name"] = AWS_REGION
if AWS_PROFILE:
    session_kwargs["profile_name"] = AWS_PROFILE
    logger.info("Using local AWS profile %s", AWS_PROFILE)

def _new_session() -> boto3.Session:
    try:
        return boto3.Session(**session_kwargs)
    except (NoCredentialsError, ClientError) as err:
        logger.warning("Falling back to default boto3 session: %s", err)
        return boto3.Session()

_session         = _new_session()
dynamodb_client  = _session.client("dynamodb")
sns_client       = _session.client("sns")

# ---------------------------------------------------------------------------
# Decorators / helpers for logging
# ---------------------------------------------------------------------------
def _log_invocation(context) -> None:
    """Emit a one‑liner at the start of each invocation."""
    logger.info(
        "Invoke %s‑%s requestId=%s",
        context.function_name  if context else "<test>",
        context.function_version if context else "<test>",
        context.aws_request_id   if context else "<test>",
    )

def error_logged(fn):
    """Decorator that logs tracebacks but re‑raises so Lambda marks failure."""
    @wraps(fn)
    def _wrapper(event, context=None):
        try:
            _log_invocation(context)
            return fn(event, context)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled error in %s: %s", fn.__name__, exc)
            raise
    return _wrapper

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ATTR_ID               = "id"
ATTR_ROLE             = "role"
ATTR_EMAIL            = "email"
ATTR_VENDOR_ID        = "vendorId"
ATTR_CATEGORY         = "category"
ATTR_EXPIRY_DATE      = "expiryDate"
ATTR_LOCATION         = "location" 
ATTR_LAT              = "lat"
ATTR_LON              = "lon"
ATTR_ALERT_RADIUS     = "alertRadius"
ATTR_ACCEPTED_TYPES   = "acceptedTypes"
ATTR_COMP_AVAIL       = "composterAvailability"

def _to_float(attr: Dict[str, Any] | None, default: float = 0.0) -> float:
    try:
        if not attr:
            return default
        if "N" in attr:
            return float(attr["N"])
        if isinstance(attr, (int, float, Decimal)):
            return float(attr)
    except (TypeError, ValueError):
        pass
    return default

def _to_bool(attr: Dict[str, Any] | None, default: bool = False) -> bool:
    if not attr:
        return default
    if "BOOL" in attr:
        return bool(attr["BOOL"])
    if "N" in attr:
        try:
            return int(attr["N"]) > 0
        except (TypeError, ValueError):
            return default
    return default

def _extract_lat_lon(item: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Return (lat, lon) regardless of top‑level or nested 'location' map."""
    if ATTR_LAT in item and ATTR_LON in item:
        return _to_float(item.get(ATTR_LAT)), _to_float(item.get(ATTR_LON))
    # Use .get("M", {}) on the result of item.get() which might be None
    loc_map = item.get(ATTR_LOCATION, {}).get("M")
    if isinstance(loc_map, dict):
        return _to_float(loc_map.get(ATTR_LAT)), _to_float(loc_map.get(ATTR_LON))
    return None, None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R_MI = 3_958.8
    phi1, phi2 = map(math.radians, (lat1, lat2))
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2 +
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R_MI * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ---------------------------------------------------------------------------
# SNS publish with diagnostics
# ---------------------------------------------------------------------------
def _publish_sns(
    *,
    topic_arn: str,
    subject: str,
    message: str,
    message_attributes: Optional[Dict[str, Dict[str, str]]] = None,
) -> bool:
    t0 = time.perf_counter()
    try:
        resp = sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message,
            MessageAttributes=message_attributes or {},
        )
        ok = resp.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200 and resp.get("MessageId")
    except ClientError as err:
        logger.error("sns.publish error: %s", err)
        ok, resp = False, {"Error": str(err)}

    duration_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "sns.publish finished in %d ms – success=%s – response=%s",
        duration_ms, ok, resp,
    )

    metric = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "Demeter/Notifications",
                "Dimensions": [["Function"], ["Topic"]],
                "Metrics": [
                    {"Name": "SNSPublishSuccess", "Unit": "Count"},
                    {"Name": "SNSPublishFail",    "Unit": "Count"},
                ],
            }],
        },
        "Function": "demeter_lambda", 
        "Topic": topic_arn.split(":")[-1],
        "SNSPublishSuccess": 1 if ok else 0,
        "SNSPublishFail":    0 if ok else 1,
    }
    logger.info(json.dumps(metric))
    return bool(ok)

# ---------------------------------------------------------------------------
# Handler: expiry alerts
# ---------------------------------------------------------------------------
@error_logged
def check_expiring_food_handler(event, context): 
    users_table = f"{TABLE_PREFIX}Users"
    topic       = os.getenv("EXPIRY_ALERT_SNS_TOPIC_ARN")
    if not topic:
        logger.error("EXPIRY_ALERT_SNS_TOPIC_ARN env var not set")
        return {"statusCode": 500, "body": "SNS topic ARN missing"}

    now_utc   = datetime.now(timezone.utc)
    processed: Set[str] = set()

    for rec in event.get("Records", []):
        if rec.get("eventName") != "INSERT":
            continue
        item = rec["dynamodb"].get("NewImage", {})
        food_id   = item.get(ATTR_ID, {}).get("S")
        vendor_id = item.get(ATTR_VENDOR_ID, {}).get("S")
        expiry_raw = item.get(ATTR_EXPIRY_DATE, {}).get("S")
        lat, lon   = _extract_lat_lon(item)
        if not all([food_id, vendor_id, expiry_raw, lat is not None, lon is not None]): 
            logger.warning("Incomplete FoodItem (id/vendor/expiry/location): %s", food_id or item)
            continue

        try:
            expiry = (
                datetime.fromisoformat(expiry_raw)
                if "T" in expiry_raw else
                datetime.strptime(expiry_raw, "%Y-%m-%d")
            )
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.error("Bad expiryDate %s on %s", expiry_raw, food_id)
            continue
        if expiry > now_utc + timedelta(days=1):
            continue

        scan = {
            "TableName": users_table,
            "FilterExpression": "#role = :cust AND attribute_exists(#alert)",
            "ExpressionAttributeNames": {
                "#role": ATTR_ROLE,
                "#alert": ATTR_ALERT_RADIUS,
                "#loc": ATTR_LOCATION,  
            },
            "ExpressionAttributeValues": {":cust": {"S": "Customer"}},
            "ProjectionExpression": f"{ATTR_ID}, {ATTR_EMAIL}, {ATTR_LAT}, "
                                    f"{ATTR_LON}, #loc, {ATTR_ALERT_RADIUS}", 
        }
        
        while True:
            try:
                resp = dynamodb_client.scan(**scan)
            except ClientError as e:
                 logger.error("DynamoDB Scan operation failed: %s", e)
                 break 

            for cust in resp.get("Items", []):
                cust_id = cust.get(ATTR_ID, {}).get("S")
                if not cust_id or cust_id in processed:
                    continue
                cust_lat, cust_lon = _extract_lat_lon(cust)
                radius = _to_float(cust.get(ATTR_ALERT_RADIUS))
                if cust_lat is None or cust_lon is None or radius <= 0:
                    continue
                if lat is not None and lon is not None:
                    if haversine_distance(lat, lon, cust_lat, cust_lon) <= radius:
                        msg = (f"Food item {food_id} from vendor {vendor_id} is "
                               "nearing expiry near your location.")
                        if _publish_sns(
                            topic_arn=topic,
                            subject="Nearby expiring food",
                            message=msg,
                            message_attributes={
                                "customerId": {"DataType": "String", "StringValue": cust_id}
                            },
                        ):
                            processed.add(cust_id)

            if "LastEvaluatedKey" not in resp:
                break
            scan["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    return {"statusCode": 200, "body": "Expiry notifications processed"}

# ---------------------------------------------------------------------------
# Handler: composter matching
# ---------------------------------------------------------------------------
@error_logged
def match_composters_handler(event, context):  
    users_table = f"{TABLE_PREFIX}Users"
    topic       = (
        os.getenv("COMPOSTER_ALERT_SNS_TOPIC_ARN")
        or os.getenv("EXPIRY_ALERT_SNS_TOPIC_ARN")
    )
    # Default radius is 10km (~6.2 miles)
    radius_mi   = _to_float({"N": os.getenv("COMPOSTER_SEARCH_RADIUS", "6.2")})
    if not topic:
        logger.error("No SNS topic ARN configured for composter alerts")
        return {"statusCode": 500, "body": "SNS topic missing"}

    processed: Set[str] = set()

    for rec in event.get("Records", []):
        if rec.get("eventName") != "INSERT":
            continue
        item = rec["dynamodb"].get("NewImage", {})
        if not _to_bool(item.get(ATTR_COMP_AVAIL)):
            continue

        food_id   = item.get(ATTR_ID, {}).get("S") or ""
        vendor_id = item.get(ATTR_VENDOR_ID, {}).get("S") or ""
        category  = (item.get(ATTR_CATEGORY, {}).get("S") or "").strip().lower()
        food_lat, food_lon = _extract_lat_lon(item)
        if food_lat is None or food_lon is None: 
            logger.warning("Skipping composter match for food item %s due to missing location", food_id or item)
            continue

        scan = {
            "TableName": users_table,
            "FilterExpression": "#role = :comp AND attribute_exists(#loc) AND attribute_exists(#types)",
            "ExpressionAttributeNames": {
                "#loc": ATTR_LOCATION, "#types": ATTR_ACCEPTED_TYPES, "#role": ATTR_ROLE
            },
            "ExpressionAttributeValues": {":comp": {"S": "Composter"}},
            "ProjectionExpression": f"{ATTR_ID}, {ATTR_EMAIL}, #loc, #types",
        }

        while True:
            try:
                 resp = dynamodb_client.scan(**scan)
            except ClientError as e:
                 logger.error("DynamoDB Scan operation failed: %s", e)
                 break 

            for comp in resp.get("Items", []):
                comp_id = comp.get(ATTR_ID, {}).get("S")
                if not comp_id or comp_id in processed:
                    continue

                comp_lat, comp_lon = None, None
                loc_map = comp.get(ATTR_LOCATION, {}).get("M")
                if isinstance(loc_map, dict):
                    comp_lat = _to_float(loc_map.get(ATTR_LAT))
                    comp_lon = _to_float(loc_map.get(ATTR_LON))

                accepted_types_str = comp.get(ATTR_ACCEPTED_TYPES, {}).get("S", "")
                accepted = {
                    t.strip().lower()
                    for t in accepted_types_str.split(",")
                    if t.strip()
                }

                if comp_lat is not None and comp_lon is not None and category and category in accepted:
                    if haversine_distance(food_lat, food_lon, comp_lat, comp_lon) <= radius_mi:
                        msg = (
                            f"Vendor {vendor_id} has unsold food "
                            f"(ID: {food_id}, category: {category}) near you that can be composted."
                        )
                        if _publish_sns(
                            topic_arn=topic,
                            subject="Composter match",
                            message=msg,
                            message_attributes={
                                "composterId": {"DataType": "String", "StringValue": comp_id}
                            },
                        ):
                            processed.add(comp_id)

            if "LastEvaluatedKey" not in resp:
                break
            scan["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    return {"statusCode": 200, "body": "Composter notifications processed"}
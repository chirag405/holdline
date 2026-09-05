"""Create the three DynamoDB tables (on-demand billing). Idempotent."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from holdline.config import get_settings

TABLES = {
    "tasks": "task_id",
    "calls": "call_id",
    "decisions": "decision_id",
}


def main() -> None:
    s = get_settings()
    ddb = boto3.client("dynamodb", region_name=s.aws_region)
    for logical, key in TABLES.items():
        name = s.table(logical)
        try:
            ddb.create_table(
                TableName=name,
                BillingMode="PAY_PER_REQUEST",
                AttributeDefinitions=[{"AttributeName": key, "AttributeType": "S"}],
                KeySchema=[{"AttributeName": key, "KeyType": "HASH"}],
            )
            print(f"creating {name} ...")
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceInUseException":
                print(f"{name} already exists")
            else:
                raise
    waiter = ddb.get_waiter("table_exists")
    for logical in TABLES:
        waiter.wait(TableName=s.table(logical))
        print(f"ready: {s.table(logical)}")


if __name__ == "__main__":
    main()

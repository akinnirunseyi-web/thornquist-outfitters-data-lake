import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext


args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "S3_SOURCE_PATH", "S3_TARGET_PATH"],
)

sc = SparkContext.getOrCreate()
glue_context = GlueContext(sc)
spark = glue_context.spark_session

job = Job(glue_context)
job.init(args["JOB_NAME"], args)

source_path = args["S3_SOURCE_PATH"]
target_path = args["S3_TARGET_PATH"]

expected_columns = {
    "cust_num",
    "first_name",
    "last_name",
    "email",
    "signup_date",
    "loyalty_tier",
    "region",
}

customers = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "false")
    .option("mode", "FAILFAST")
    .csv(source_path)
)

missing_columns = expected_columns - set(customers.columns)

if missing_columns:
    raise ValueError(
        f"Missing required customer columns: {sorted(missing_columns)}"
    )

# Keep identifiers as strings to preserve leading zeros.
customers = customers.select(
    "cust_num",
    "first_name",
    "last_name",
    "email",
    "signup_date",
    "loyalty_tier",
    "region",
)

row_count = customers.count()

# Overwrite makes reruns idempotent instead of appending duplicate rows.
customers.write.mode("overwrite").format("parquet").save(target_path)

print(f"Source: {source_path}")
print(f"Destination: {target_path}")
print(f"Customer rows written: {row_count}")
print(f"Columns: {customers.columns}")

job.commit()

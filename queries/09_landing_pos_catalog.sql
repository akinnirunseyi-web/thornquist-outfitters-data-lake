-- Run once in Athena against thornquist_outfitters. Review an existing table before replacing it.
CREATE EXTERNAL TABLE IF NOT EXISTS thornquist_outfitters.landing_pos (
  transaction_id string,
  store_id string,
  store_name string,
  region string,
  sale_date string,
  category string,
  product_name string,
  quantity string,
  unit_price string,
  payment_method string,
  cust_num string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES (
  'separatorChar' = ',',
  'quoteChar' = '"'
)
STORED AS TEXTFILE
LOCATION 's3://thornquist-data-lake-2026102/landing/pos/'
TBLPROPERTIES ('skip.header.line.count' = '1');

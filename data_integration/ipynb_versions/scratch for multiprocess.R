# Test generate data product from db
library(tidyverse)
library(RSQLite)
library(DBI)

project_root_dir = '//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data/Data Integration - All Months' 

db_path='ituran_synchromatics_data.sqlite'
route_stop_table_name='route_stop'
stop_event_table_name='stop_time'
driver_schedule_table_name='vehicle_assignment'
warning_table_name='warning'
hotspot_record_table_name='hotspot_data_product'
longitudinal_record_table_name='longitudinal_data_product'
if_exists='append'

conn = dbConnect(RSQLite::SQLite(), file.path(project_root_dir, db_path))


query = "select * from stop_time where arrived_at >= datetime('2018-04-01 00:00:00') and arrived_at <= datetime('2018-04-30 23:59:59')"

query = "select * from stop_time where arrived_at >= datetime('2018-04-01 00:00:00') and arrived_at <= datetime('2018-04-30 23:59:59')"

query = "select * from vehicle_assignment limit 10"# where arrived_at >= datetime('2018-02-01 00:00:00') and arrived_at <= datetime('2018-02-28 23:59:59')"

query = "select * from warning limit 10"# where arrived_at >= '2018-02-01 00:00:00' and arrived_at <= '2018-02-28 23:59:59'"

db = dbGetQuery(conn, query)

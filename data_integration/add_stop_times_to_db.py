# create a postgreSQL database

# create a driver_schedule table, and
# for each month, and for each route, add all records to that single table

# we may care to sort the records before adding to the database table

# first, we need to know if it is safe to use vehicle_assignment_id as the
# primary key for driver schedule records, so we test for uniqueness across all
# data files: for each VehiclesThatRanRoute file across all routes and months,
# read vehicle_assignment_id values into an array, count the unique array
# entries and compare for equality with the array length.
from os import path, walk
import pandas as pd
from sqlalchemy import create_engine


def find_duplicates(df, index_col='stop_time_id', duplicate_col='route_id'):
  unique_route_ids = df.loc[:, duplicate_col].unique()

  for unique_route_id in unique_route_ids:
    routes = df.loc[df[duplicate_col] == unique_route_id]

    # display unique record count and total record count for comparison
    print(routes.shape[0])
    print(routes.loc[:, index_col].unique().shape[0])

data_root_dir = 'data_sources'

stop_time_data = []

for dir, subdirs, files in walk(data_root_dir):
  # we assume that files only exist at the nodes
  if len(files) > 0:
    # we assume that only one driver schedule file exists in the current dir
    file_name_indices = [
      file.find('_StopTimes_') >= 0 for file in files]

    try:
      file_name_index = file_name_indices.index(True)
    except:
      print('Stop time file not found in {}'.format(dir))
      continue

    file_name = files[file_name_index]
    file_path = path.join(dir, file_name)

    stop_time_data.append(pd.read_table(file_path))

stop_time_data = pd.concat(
  stop_time_data, ignore_index=True, verify_integrity=True)

# count the unique stop_tim_id and compare with the number of records to
# identify duplicates (and do it per route in case duplicates occur across
# routes but not within a single route - which is okay) we learn that indeed
# the stop ids are unique within a given route
# find_duplicates(stop_time_data)

# drop duplicates if found
stop_time_data.drop_duplicates(inplace=True)

# we temporarily also drop records with missing values to prove our concept.
# Key attributes that require values include 1) stop_id, 2) route_id,
# 3) vehicle_id, 4) arrived_at, 5) departed_at, and 6) stop_time_id.
# TODO: Infer missing values where possible using warning and route data
key_column_names = ['stop_id', 'vehicle_id', 'route_id',
                    'stop_time_id', 'arrived_at', 'departed_at']

stop_time_data.dropna(subset=key_column_names, inplace=True)

# we make no assumption about the order in which source xlsx files are input
stop_time_data.sort_values(['arrived_at', 'departed_at'], inplace=True)

# since stop_time_ids are only unique within a single route, we must create a
# composite primary key using both route_id and stop_time_id. Set drop=False to
# retain the 'source' columns. Because we don't yet know how this results in a 
# SQLite PK, just reset the indices for now (since some records were dropped)
# stop_time_data = stop_time_data.set_index(
# ['route_id', 'stop_time_id'], drop=False)
stop_time_data.set_index(pd.RangeIndex(stop_time_data.shape[0]), inplace=True)

db_path = 'sqlite:///ituran_synchromatics_data.db'

db = create_engine(db_path)

# poor performance has been observed when adding more than one million records
# at a time
stop_time_data.to_sql(
  'stop_time', db, if_exists='replace', chunksize=1000000)

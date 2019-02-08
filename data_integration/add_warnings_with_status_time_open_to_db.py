# create a postgreSQL database

# create a driver_schedule table, and
# for each month, and for each route, add all records to that single table

# we may care to sort the records before adding to the database table

# first, we need to know if it is safe to use vehicle_assignment_id as the
# primary key for driver schedule records, so we test for uniqueness across all
# data files: for each VehiclesThatRanRoute file across all routes and months,
# read vehicle_assignment_id values into an array, count the unique array
# entries and compare for equality with the array length.
import numpy as np
from os import path, listdir
import pandas as pd
from sqlalchemy import create_engine


def preprocess_warning_name(elem):
  warning_name = elem.split(' - StatusTimeOpen:')[0]
  return warning_name if warning_name in warning_name_list else None

def preprocess_bus_number(elem):
  return elem.split()[-1]

#assume that the warnings folder only has warning spreadsheet files as children
data_root_dir = 'warnings'

warning_data = []

warning_name_list = [
  'ME - Pedestrian Collision Warning', 'ME - Pedestrian In Range Warning',
  'PCW-LF', 'PCW-LR', 'PCW-RR', 'PDZ - Left Front', 'PDZ-LR', 'PDZ-R',
  'Safety - Braking - Aggressive', 'Safety - Braking - Dangerous']

for file_name in listdir(data_root_dir):
  file_path = path.join(data_root_dir, file_name)

  # only read columns loc_time (0), Vehicle Name (2), Address (7),
  # warning_name (9), Latitude (11), Longitude (12), and skip the Ituran header
  # (first 7 rows)
  df = pd.read_excel(
    file_path, skiprows=[0, 1, 2, 3, 4, 5, 6, 7], usecols=[0, 2, 7, 9, 11, 12],
    names=['loc_time', 'bus_number', 'address', 'warning_name', 'latitude',
           'longitude'], header=None, parse_dates=[0], dtype={
      0: object, 2: object, 7: object, 9: object, 11: np.float64,
      12: np.float64})
  # print(df.describe())
  # print(df.head().loc[:, 'warning_name'])

  # remove extraneous StatusTimeOpen suffix from warning messages and set other
  # messages to null, then drop those null records
  df.loc[:, 'warning_name'] = df.loc[:, 'warning_name'].apply(
    preprocess_warning_name)

  df.loc[:, 'bus_number'] = df.loc[:, 'bus_number'].apply(
    preprocess_bus_number).astype(np.uint32)
  # print(df.head().loc[:, 'warning_name'])

  df.dropna(subset=['warning_name'], inplace=True)
  # print(df.describe())
  # print(df.head().loc[:, 'warning_name'])

  print(df.head(2))
  print(df.dtypes)

  warning_data.append(df)

warning_data = pd.concat(
  warning_data, ignore_index=True, verify_integrity=True)

print('init warning_data:\n{}'.format(warning_data.describe()))

# count the unique stop_tim_id and compare with the number of records to
# identify duplicates (and do it per route in case duplicates occur across
# routes but not within a single route - which is okay) we learn that indeed
# the stop ids are unique within a given route
# find_duplicates(warning_data)

# drop duplicates if found
warning_data.drop_duplicates(inplace=True)

print('de-duplicated warning_data:\n{}'.format(warning_data.describe()))
print('\n{}'.format(warning_data.head()))

# we temporarily also drop records with missing values to prove our concept.
# Key attributes that require values include 1) __, 2) route_id,
# 3) vehicle_id, 4) arrived_at, 5) departed_at, and 6) stop_time_id. For now,
# we exclude the stop_id because many relevant records have missing stop_ids.
# TODO: Infer missing values where possible using warning and route data
# key_column_names = ['route_id', 'vehicle_id', 'arrived_at', 'departed_at']
#
# warning_data.dropna(subset=key_column_names, inplace=True)

# we make no assumption about the order in which source files are input
warning_data.sort_values(['loc_time', 'bus_number'], inplace=True)

# reset indices after sorting records
warning_data.set_index(pd.RangeIndex(warning_data.shape[0]), inplace=True)

# excel_writer = pd.ExcelWriter('processed_warnings.xlsx')
#
# chunk_size = pow(2, 20) - 1
#
# idx_limit = warning_data.shape[0]
#
# for i in range(int(ceil(idx_limit / chunk_size))):
#   chunk = warning_data.iloc[i * chunk_size:max((i + 1) * chunk_size, idx_limit)]
#
#   print('{}_th chunk_data:\n{}\n{}\n'.format(i, chunk.describe(), chunk.head()))
#
#   chunk.to_excel(excel_writer, 'warnings_{}'.format(i), index=False)
#
# excel_writer.save()

db_path = 'sqlite:///ituran_synchromatics_data.sqlite'

db = create_engine(db_path)

# poor performance has been observed when adding more than one million records
# at a time
warning_data.to_sql(
  'warning', db, if_exists='replace', chunksize=1000000, index=False)

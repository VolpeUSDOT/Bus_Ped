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
from os import path, walk
import pandas as pd
from sqlalchemy import create_engine

data_root_dir = 'data_sources'

vehicle_assignment_data = []

for dir, subdirs, files in walk(data_root_dir):
  # we assume that files only exist at the nodes
  if len(files) > 0:
    # we assume that only one driver schedule file exists in the current dir
    try:
      file_name_indices = [
        file.find('_VehiclesThatRanRoute_') >= 0 for file in files]

      file_name_index = file_name_indices.index(True)
      file_name = files[file_name_index]
      file_path = path.join(dir, file_name)

      # forget using np.unicode_ for strings since pandas treats them as objects
      # we can specify the data type since none of the values are null
      df = pd.read_table(
        file_path, usecols=[0, 1, 2, 3, 5, 6, 11, 12, 13, 14],
        header=None, skiprows=[0], parse_dates=['start_time', 'end_time'],
        names=['vehicle_assignment_id', 'vehicle_id', 'route_id', 'driver_id',
               'start_time', 'end_time', 'bus_number', 'first_name',
               'last_name', 'badge_number'],
        dtype={'vehicle_assignment_id': np.uint64, 'vehicle_id': np.uint32,
               'route_id': np.uint32, 'driver_id': np.uint32,
               'start_time': object, 'end_time': object,
               'bus_number': np.uint32, 'first_name': object,
               'last_name': object, 'badge_number': np.uint32})

      print(df.head(2))
      print(df.dtypes)

      vehicle_assignment_data.append(df)
    except Exception as e:
      print('Driver schedule file not found in {}'.format(dir))
      print(e)
      continue

vehicle_assignment_data = pd.concat(
  vehicle_assignment_data, ignore_index=True, verify_integrity=True)

# records of runs that span two days may appear once for each day depending on
# how the Excel exports were preformed, and should be dropped
vehicle_assignment_data.drop_duplicates(inplace=True)

# we temporarily also drop records with missing values to prove our concept.
# Key attributes that require values include 1) vehicle_assessment_id,
# 2) vehicle_id, 3) BusNumber, 4) driver_id (at least for longitudinal),
# 5) start_time, and 6) end_time.
# TODO: Infer missing values where possible using warning and route data
key_column_names = ['vehicle_assignment_id', 'vehicle_id', 'bus_number',
                    'driver_id', 'start_time', 'end_time']

vehicle_assignment_data.dropna(subset=key_column_names, inplace=True)

# we make no assumption about the order in which source xlsx files are input
vehicle_assignment_data.sort_values(['start_time', 'end_time'], inplace=True)

# after removing duplicate records, vehicle_assignment_ids will be unique and
# can be used as the primary key of the vehicle_assignment table. Because we
# don't yet know how this results in a SQLite PK, just reset the indices for now
# vehicle_assignment_data.set_index('vehicle_assignment_id', inplace=True)
vehicle_assignment_data.set_index(
  pd.RangeIndex(vehicle_assignment_data.shape[0]), inplace=True)

print(vehicle_assignment_data.describe())
print(df.dtypes)

db_path = 'sqlite:///ituran_synchromatics_data.sqlite'

db = create_engine(db_path)

# poor performance has been observed when adding more than one million records
# at a time
vehicle_assignment_data.to_sql(
  'vehicle_assignment', db, if_exists='replace', chunksize=1000000, index=False)

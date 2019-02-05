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

data_root_dir = 'data_sources'

vehicle_assignment_data = []

for dir, subdirs, files in walk(data_root_dir):
  # we assume that files only exist at the nodes
  if len(files) > 0:
    # we assume that only one driver schedule file exists in the current dir
    file_name_indices = [
      file.find('_VehiclesThatRanRoute_') >= 0 for file in files]

    try:
      file_name_index = file_name_indices.index(True)

      file_name = files[file_name_index]

      file_path = path.join(dir, file_name)

      vehicle_assignment_data.append(pd.read_table(
        file_path, usecols=[0, 1, 2, 3, 5, 6, 11, 12, 13, 14],
        header=['vehicle_assignment_id', 'vehicle_id', 'route_id', 'driver_id',
                'start_time', 'end_time', 'bus_number', 'first_name',
                'last_name', 'badge_number']))
    except:
      print('Driver schedule file not found in {}'.format(dir))
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

db_path = 'sqlite:///ituran_synchromatics_data.db'

db = create_engine(db_path)

# poor performance has been observed when adding more than one million records
# at a time
vehicle_assignment_data.to_sql(
  'vehicle_assignment', db, if_exists='replace', chunksize=1000000)

# create a postgreSQL database

# create a driver_schedule table, and
# for each month, and for each route, add all records to that single table

# we may care to sort the records before adding to the database table

# first, we need to know if it is safe to use vehicle_assignment_id as the
# primary key for driver schedule records, so we test for uniqueness across all
# data files: for each VehiclesThatRanRoute file across all routes and months,
# read vehicle_assignment_id values into an array, count the unique array
# entries and compare for equality with the array length.
import argparse
import numpy as np
from os import path, listdir
import pandas as pd
from sqlalchemy import create_engine


def write_warning_data_to_excel(data, file_name='unassigned_warnings'):
  from math import ceil

  excel_writer = pd.ExcelWriter(file_name + '.xlsx')

  chunk_size = pow(2, 20) - 1

  idx_limit = data.shape[0]

  for i in range(int(ceil(idx_limit / chunk_size))):
    chunk = data.iloc[i * chunk_size:max((i + 1) * chunk_size, idx_limit)]

    print('{}_th chunk_data:\n{}\n{}\n'.format(i, chunk.describe(), chunk.head()))

    chunk.to_excel(excel_writer, 'warnings_{}'.format(i), index=False)

  excel_writer.save()


def preprocess_bus_number(elem):
  return elem.split()[-1]


def read_warning_data(data_dir):
  #assume that the warnings folder only has warning spreadsheet files as children
  warning_data = []

  rows_to_skip = [0, 1, 2, 3, 4, 5, 6, 7]
  cols_to_use = [0, 1, 3, 4, 5, 6]
  dtypes = {0: object, 1: object, 3: object, 4: object, 5: object, 6: object}

  for file_name in listdir(data_dir):
    try:
      file_path = path.join(data_dir, file_name)

      # only read columns loc_time (0), Vehicle Name (2), Address (7),
      # warning_name (9), Latitude (11), Longitude (12), and skip the Ituran header
      # (first 7 rows)
      df = pd.read_excel(
        file_path, skiprows=rows_to_skip, usecols=cols_to_use,
        names=['loc_time', 'bus_number', 'address', 'warning_name', 'latitude',
               'longitude'], header=None, parse_dates=[0], dtype=dtypes)
      # print(df.describe())
      # print(df.head().loc[:, 'warning_name'])
      df.drop(df.query('address.str.contains(\'Last known:\')',
                       engine='python').index, inplace=True)

      df.loc[:, 'bus_number'] = df.loc[:, 'bus_number'].apply(
        preprocess_bus_number).astype(np.uint32)
      # print(df.head().loc[:, 'warning_name'])

      df.loc[:, 'latitude'] = df.loc[:, 'latitude'].astype(np.float64)
      # print(df.head().loc[:, 'warning_name'])

      df.loc[:, 'longitude'] = df.loc[:, 'longitude'].astype(np.float64)
      # print(df.head().loc[:, 'warning_name'])

      df.dropna(subset=['warning_name', 'loc_time'], inplace=True)
      # print(df.describe())
      # print(df.head().loc[:, 'warning_name'])

      print(df.head(2))
      print(df.dtypes)

      warning_data.append(df)
    except Exception as e:
      print(e)
      print(file_name)
      exit()

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

  return warning_data


if __name__ == "__main__":
  parser = argparse.ArgumentParser()

  parser.add_argument('--db_path', default='ituran_synchromatics_data.sqlite')
  parser.add_argument('--warning_table_name', default='warning')
  parser.add_argument('--warning_data_dir', default='warnings')
  parser.add_argument('--if_exists', default='append')

  args = parser.parse_args()

  db = create_engine('sqlite:///' + args.db_path)

  warning_data = read_warning_data(args.warning_data_dir)
  # poor performance has been observed when adding more than one million records
  # at a time
  warning_data.to_sql(args.warning_table_name, db, if_exists=args.if_exists,
                      chunksize=1000000, index=False)
import argparse
import numpy as np
from os import path, listdir
import pandas as pd
from sqlalchemy import create_engine

# This script creates or replaces a table in the database at the supplied
# path that contains the set of stops for each of five Downtown DASH routes. The
# source Excel files are hand-crafted and assumed to be perfect.


def read_route_stop_data(dir_path):
  route_stop_data = []

  for file_name in listdir(dir_path):
    # we assume that all files exist at the root
    file_path = path.join(dir_path, file_name)

    # pandas treats strings as objects
    df = pd.read_excel(file_path, dtype={
      'route_id': np.uint32, 'route_name': object, 'stop_id': np.uint32,
      'stop_name': object, 'latitude': np.float64, 'longitude': np.float64,
      'heading': object, 'sequence': np.uint8, 'is_terminal': np.bool_})
    route_stop_data.append(df)

  route_stop_data = pd.concat(
    route_stop_data, ignore_index=True, verify_integrity=True)

  route_stop_data.set_index(
    pd.RangeIndex(route_stop_data.shape[0]), inplace=True)

  return route_stop_data


if __name__ == "__main__":
  parser = argparse.ArgumentParser()

  parser.add_argument(
    'db_path', default='ituran_synchromatics_data.sqlite')
  parser.add_argument(
    'route_stop_table_name', default='route_stop')
  parser.add_argument(
    'data_root_dir', default='route_stops')
  args = parser.parse_args()

  db_path = 'sqlite://' + args.db_path

  db = create_engine(db_path)

  route_stop_data = read_route_stop_data(args.data_root_dir)

  # print(route_stop_data.head(2))
  # print(route_stop_data.dtypes)

  # poor performance has been observed when adding more than one million records
  # at a time
  route_stop_data.to_sql(args.route_stop_table_name, db, if_exists='replace',
                         chunksize=1000000, index=False)

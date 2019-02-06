# create a postgreSQL database

# create a driver_schedule table, and
# for each month, and for each route, add all records to that single table

# we may care to sort the records before adding to the database table

# first, we need to know if it is safe to use vehicle_assignment_id as the
# primary key for driver schedule records, so we test for uniqueness across all
# data files: for each VehiclesThatRanRoute file across all routes and months,
# read vehicle_assignment_id values into an array, count the unique array
# entries and compare for equality with the array length.
from os import path, listdir
import pandas as pd
from sqlalchemy import create_engine


def read_route_stop_data(dir_path):
  route_stop_data = []

  for file_name in listdir(dir_path):
    # we assume that all files exist at the root
    file_path = path.join(dir_path, file_name)

    route_stop_data.append(pd.read_excel(file_path))

  route_stop_data = pd.concat(
    route_stop_data, ignore_index=True, verify_integrity=True)

  return route_stop_data


if __name__ == "__main__":
  data_root_dir = 'route_stops'

  route_stop_data = read_route_stop_data(data_root_dir)

  # since these spreadsheets are hand-crafted, we assume no missing or duplicate
  # records

  route_stop_data.set_index(pd.RangeIndex(route_stop_data.shape[0]), inplace=True)

  db_path = 'sqlite:///ituran_synchromatics_data.sqlite'

  db = create_engine(db_path)

  # poor performance has been observed when adding more than one million records
  # at a time
  route_stop_data.to_sql(
    'route_stop', db, if_exists='replace', chunksize=1000000, index=False)

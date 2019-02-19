import argparse
import numpy as np
from os import path, walk
import pandas as pd
from sqlalchemy import create_engine
from add_route_stops_to_db import read_route_stop_data

# This script creates or replaces a table in the database at the supplied
# path that contains the set of stops for each of five Downtown DASH routes


def find_duplicates(df, index_col='stop_time_id', duplicate_col='route_id'):
  unique_route_ids = df.loc[:, duplicate_col].unique()

  for unique_route_id in unique_route_ids:
    routes = df.loc[df[duplicate_col] == unique_route_id]

    # display unique record count and total record count for comparison
    print(routes.shape[0])
    print(routes.loc[:, index_col].unique().shape[0])

def preprocess_bus_number(elem):
  return elem.split()[-1]

# TODO: convert print statements to log statements
def read_stop_time_data(data_root_dir):
  stop_time_data = []

  for dir, subdirs, files in walk(data_root_dir):
    # we assume that files only exist at the nodes
    if len(files) > 0:
      # we assume that only one driver schedule file exists in the current dir
      file_name_indices = [
        file.find('_StopTimes_') >= 0 for file in files]

      try:
        file_name_index = file_name_indices.index(True)

        file_name = files[file_name_index]

        file_path = path.join(dir, file_name)

        df = pd.read_csv(
          file_path, sep='\t', usecols=[0, 1, 2, 4, 5, 6, 7, 8, 9, 12],
          dtype={'stop_id': object, 'route_id': np.uint32,
                 'vehicle_id': np.uint16, 'arrived_at': object,
                 'arrival_latitude': np.float64, 'arrival_longitude': np.float64,
                 'departed_at': object, 'departure_latitude': np.float64,
                 'departure_longitude': np.float64, 'stop_time_id': np.uint64},
          parse_dates=['arrived_at', 'departed_at'])

        # convert null stop_ids to a zero value
        df['stop_id'] = np.array(
          df['stop_id'].values, dtype=np.float32).astype(np.uint32)

        print(df.head(2))
        print(df.dtypes)

        stop_time_data.append(df)
      #TODO: discover and handle distinct exceptions rather than catch all
      except Exception as e:
        print(e)
        continue

  stop_time_data = pd.concat(
    stop_time_data, ignore_index=True, verify_integrity=True)

  # count the unique stop_tim_id and compare with the number of records to
  # identify duplicates (and do it per route in case duplicates occur across
  # routes but not within a single route - which is okay) we learn that indeed
  # the stop ids are unique within a given route
  # ...we don't call this anymore having observed that no duplicates exist (for now)
  # find_duplicates(stop_time_data)

  # drop duplicates if found
  stop_time_data.drop_duplicates(inplace=True)

  # we temporarily also drop records with missing values to prove our concept.
  # Key attributes that require values include 1) __, 2) route_id,
  # 3) vehicle_id, 4) arrived_at, 5) departed_at, and 6) stop_time_id. For now,
  # we exclude the stop_id because many relevant records have missing stop_ids.
  # TODO: Infer missing values where possible using warning and route data
  key_column_names = ['route_id', 'vehicle_id', 'arrived_at', 'departed_at']

  stop_time_data.dropna(subset=key_column_names, inplace=True)

  # we make no assumption about the order in which source files are input
  stop_time_data.sort_values(
    ['route_id', 'vehicle_id', 'arrived_at', 'departed_at'], inplace=True)

  # reset indices after removing some records
  stop_time_data.set_index(pd.RangeIndex(stop_time_data.shape[0]), inplace=True)

  return stop_time_data
# we must identify terminal stop records and collapse sequences of records of a
# single terminal into a single record. We extract the set of terminal stops
# from the 'route_stop' table in the existing database

# get terminal stops from Excel in case a route stop table has not yet been
# created

def prune_stop_time_data(stop_time_data, route_stop_data):
  terminal_stop_data = route_stop_data.loc[
    route_stop_data.loc[:, 'sequence'] == 1]

  terminal_stop_time_data = []

  # TODO handle discontinuity at 12AM.
  # do any records have timestamps between 2130 and 0030?
  for stop_id in terminal_stop_data['stop_id']:
    terminal_stop_time_data.append(
      stop_time_data[stop_time_data['stop_id'] == stop_id])

  terminal_stop_time_data = pd.concat(terminal_stop_time_data)

  print('terminal_stop_time_data:\n{}'.format(terminal_stop_time_data.describe()))

  unidentified_stop_time_data = stop_time_data.loc[
    pd.isnull(stop_time_data.loc[:, 'stop_id'])]

  # print('unidentified_stop_time_data:\n{}'.format(unidentified_stop_time_data.describe()))

  # TODO: account for runs that begin at a stop other than the terminal

  combined_stop_time_data = pd.concat(
    [terminal_stop_time_data, unidentified_stop_time_data])

  # order by index so that we can find contiguous sequences
  combined_stop_time_data.sort_index(inplace=True)

  # print('combined_stop_time_data:\n{}'.format(combined_stop_time_data.describe()))

  # construct valid terminal stop records
  #TODO: split the compute across a pool of threads, perhaps per time unit
  result_data = []

  count = 1
  seq_len = 1

  head_record = combined_stop_time_data.iloc[0]
  head_index = combined_stop_time_data.index[0]

  # ensure head_record is never a BLANK
  while head_record.loc['stop_id'].squeeze() == 0 \
      and count < combined_stop_time_data.shape[0]:
    head_record = combined_stop_time_data.iloc[count]

    count += 1

  tail_record = head_record
  tail_index = head_index

  while count < combined_stop_time_data.shape[0]:
    current_record = combined_stop_time_data.iloc[count]

    # TODO: infer stop_ids from records with null stop ids (but skip them for now)
    while current_record.loc['stop_id'].squeeze() == 0 \
        and count < combined_stop_time_data.shape[0] - 1:
      seq_len += 1

      count += 1

      current_record = combined_stop_time_data.iloc[count]

    current_index = combined_stop_time_data.index[count]

    if current_index == head_index + seq_len \
        and current_record.loc['stop_id'].squeeze() == \
        head_record.loc['stop_id'].squeeze():
      tail_record = current_record

      tail_index = current_index

      seq_len += 1
    else:
      if head_index == tail_index:
        # no use in performing unnecessary computation
        result_data.append(head_record)
      else:
        result_record = pd.Series(head_record)

        result_record.loc[
          ['departed_at', 'departure_latitude', 'departure_longitude']
        ] = tail_record.loc[
          ['departed_at', 'departure_latitude', 'departure_longitude']]

        result_data.append(result_record)

      head_record = current_record
      head_index = current_index

      tail_record = current_record
      tail_index = current_index

      seq_len = 1

    count += 1

  print('count: {}'.format(count))

  result_data = pd.DataFrame(
    result_data)

  print('result_data:\n{}'.format(result_data.describe()))

  print('stop_time_data pre-drop:\n{}'.format(stop_time_data.describe()))

  # replace original terminal stop records with corrected records
  stop_time_data.drop(combined_stop_time_data.index, inplace=True)

  print('stop_time_data post-drop:\n{}'.format(stop_time_data.describe()))

  # reset indices after removing some records
  # stop_time_data.set_index(pd.RangeIndex(stop_time_data.shape[0]), inplace=True)

  # print('stop_time_data pre-append:\n{}'.format(stop_time_data.describe()))

  stop_time_data = stop_time_data.append(result_data, ignore_index=True)

  print('stop_time_data post-append:\n{}'.format(stop_time_data.describe()))

  # place the collapsed records just appended into their original positions
  stop_time_data.sort_values(
    ['route_id', 'vehicle_id', 'arrived_at', 'departed_at'], inplace=True)

  # reset indices (even though they will not make their way into the db)
  stop_time_data.set_index(pd.RangeIndex(stop_time_data.shape[0]), inplace=True)

  return stop_time_data

def output_to_excel(data_root_dir, stop_time_data):
  # write outpur to Excel for inspection
  excel_writer = pd.ExcelWriter(
    path.join(data_root_dir, 'processed_stop_times.xlsx'))

  stop_time_data.to_excel(excel_writer, 'StopTimes', index=False)

  excel_writer.save()

if __name__ == "__main__":
  parser = argparse.ArgumentParser()

  parser.add_argument(
    'db_path', default='ituran_synchromatics_data.sqlite')
  parser.add_argument(
    'stop_event_table_name', default='stop_time')
  parser.add_argument(
    'root_stop_time_data_dir', default='data_sources')
  parser.add_argument(
    'root_route_stop_data_dir', default='route_stops')
  args = parser.parse_args()

  db_path = 'sqlite://' + args.db_path

  db = create_engine(db_path)

  stop_time_data = read_stop_time_data(args.root_stop_time_data_dir)

  # read route stops to get terminal stop ids
  route_stop_data = read_route_stop_data(args.root_route_stop_data_dir)

  stop_time_data = prune_stop_time_data(stop_time_data, route_stop_data)

  # poor performance has been observed when adding more than one million records
  # at a time
  stop_time_data.to_sql(args.stop_event_table_name, db, if_exists='replace',
                        chunksize=1000000, index=False)

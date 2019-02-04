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
from add_routes_to_db import read_route_stop_data


def find_duplicates(df, index_col='stop_time_id', duplicate_col='route_id'):
  unique_route_ids = df.loc[:, duplicate_col].unique()

  for unique_route_id in unique_route_ids:
    routes = df.loc[df[duplicate_col] == unique_route_id]

    # display unique record count and total record count for comparison
    print(routes.shape[0])
    print(routes.loc[:, index_col].unique().shape[0])

# TODO: convert print statements to log statements
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

      file_name = files[file_name_index]

      file_path = path.join(dir, file_name)

      stop_time_data.append(pd.read_table(file_path))
    except:
      print('Stop time file not found in {}'.format(dir))
      continue

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

# we must identify terminal stop records and collapse sequences of records of a
# single terminal into a single record. We extract the set of terminal stops
# from the 'route_stop' table in the existing database

# get terminal stops
route_stop_data = read_route_stop_data('route_stops')

terminal_stop_data = route_stop_data.loc[
  route_stop_data.loc[:, 'StopSequence'] == 1]

terminal_stop_time_data = []

# TODO handle discontinuity at 12AM.
# do any records have timestamps between 2130 and 0030?
for stop_id in terminal_stop_data.loc[:, 'StopId']:
  terminal_stop_time_data.append(
    stop_time_data.loc[stop_time_data.loc[:, 'stop_id'] == stop_id])

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

# construct correct terminal stop records
result_data = []

count = 1
seq_len = 1

head_record = combined_stop_time_data.iloc[0]
head_index = combined_stop_time_data.index[0]

# ensure head_record is never a BLANK
while pd.isnull(head_record.loc['stop_id'].squeeze())\
    and count < combined_stop_time_data.shape[0]:
  head_record = combined_stop_time_data.iloc[count]

  count += 1

tail_record = head_record
tail_index = head_index

while count < combined_stop_time_data.shape[0]:
  current_record = combined_stop_time_data.iloc[count]

  # TODO: infer stop_ids from records with null stop ids (but skip them for now)
  while pd.isnull(current_record.loc['stop_id'].squeeze()) \
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

      # print('\nrecord range:\n{}'.format(
      #   combined_stop_time_data.loc[head_index:tail_index]))
      # for idx in range(head_index, tail_index + 1):
      #   print(combined_stop_time_data.loc[idx])

      # print('\ncollapsed to:\n{}'.format(result_record))

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

# write outpur to Excel for inspection
# excel_writer = pd.ExcelWriter(
#   path.join(data_root_dir, 'processed_stop_times.xlsx'))
#
# stop_time_data.to_excel(excel_writer, 'StopTimes', index=False)
#
# excel_writer.save()

db_path = 'sqlite:///ituran_synchromatics_data.db'

db = create_engine(db_path)

# poor performance has been observed when adding more than one million records
# at a time
stop_time_data.to_sql('stop_time', db, if_exists='replace', chunksize=1000000)

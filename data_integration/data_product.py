import argparse
from datetime import datetime
import numpy as np
import pandas as pd


def convert_stop_time_to_datetime(element):
  return datetime.strptime(element[0], '%m/%d/%Y %H:%M')


# we assume that the input format and data is perfect
def read_schedule_csv(array_csv):
  df = pd.read_csv(array_csv)
  array = df.values

  array = np.concatenate((np.concatenate(
    (array[:, 1:4], array[:, 5:7]),
    axis=1), np.expand_dims(array[:, 11], 1)), axis=1)

  array[:, 3] = np.apply_along_axis(
    convert_stop_time_to_datetime, 1, np.expand_dims(array[:, 3], 1))

  array[:, 4] = np.apply_along_axis(
    convert_stop_time_to_datetime, 1, np.expand_dims(array[:, 4], 1))

  return array


# we assume that the input format and data is perfect
def read_runs_csv(array_csv):
  df = pd.read_csv(array_csv)
  array = df.values

  array = np.concatenate((array[:, 0:3], array[:, 4:10]), axis=1)

  array[:, 3] = np.apply_along_axis(
    convert_stop_time_to_datetime, 1, np.expand_dims(array[:, 3], 1))

  array[:, 6] = np.apply_along_axis(
    convert_stop_time_to_datetime, 1, np.expand_dims(array[:, 6], 1))

  return array


# we assume that the input format and data is perfect
def read_per_bound_route_csvs(run_bound_file_paths):
  """
  Args:
    run_bound_file_paths: a 2-tuple of file paths to CSVs containing
    representations of the north or east bound and south or west bound stop
    sequences of a given route.
  """
  per_bound_stops = {}

  for name, file_path in run_bound_file_paths.items():
    df = pd.read_csv(file_path)
    array = df.values
    # columns 0=RouteID and 1=RouteName to be validated later, and
    # column 3=StopName is not relevant
    per_bound_stops[name] = np.concatenate(
      (array[:, 0:3], array[:, 4:]), axis=1)

  return per_bound_stops


def convert_loc_time_to_datetime(element):
  return datetime.strptime(element[0], '%m/%d/%Y %H:%M:%S')

def extract_bus_number_from_vehicle_name(element):
  return int(element[0].split()[-1])


# we assume that the input format and data is perfect
def read_warnings_csv(warnings_csv):
  df = pd.read_csv(warnings_csv)
  array = df.values

  array[:, 0] = np.apply_along_axis(
    convert_loc_time_to_datetime, 1, np.expand_dims(array[:, 0], 1))

  array[:, 1] = np.apply_along_axis(
    extract_bus_number_from_vehicle_name, 1, np.expand_dims(array[:, 1], 1))

  return array


class IntermediateRun:
  def __init__(self, route_id, route_name, heading, initial_stop, terminal_stop,
               vehicle_id=None, driver_id=None, start_time=None, end_time=None,
               warning_list=None):
    self.route_id = route_id
    self.route_name = route_name
    self.heading = heading
    self.initial_stop = initial_stop
    self.terminal_stop = terminal_stop
    self.vehicle_id = vehicle_id
    self.driver_id = driver_id
    self.start_time = start_time
    self.end_time = end_time
    self.warning_list = warning_list

  def __str__(self):
    return '[{}, {}, {}, {}, {}]'.format(
      self.route_id, self.heading, self.vehicle_id, self.start_time,
      self.end_time)


# create a intermediate_run_product_array
# read runs_csv
# read route_csvs
# from route_csvs construct a unique_ordered_stop_array
# identify the indices where the first stop in the unique_ordered_stop_array
# occurs in the runs_csv
# for each index, extract a sub_array of stop_ids equal to the length of the
# unique_ordered_stop_array and starting from the index
# then compare the sub_array with the stop_array for equality
# if equal, create a run record and concatenate the order in which it occurred
# to its end, thn append the record to the intermediate_run_product_array

# one problem is that we want to treat a sequence of northbound/eastbound stops,
# followed by a sequence of southbound/westbound stops as a single run, but it
# may be the case that the data representing one half of such a run is
# invalid/imperfect.
# the product has a start time, end time, heading, route_id, vehicle_id

# run definition. any sequence of stops starting with the initial stop and
# ending with the terminal stop of a single bound of a route for which all stops
# in the sequence are monotonically increasing in their order, but allowing for
# stops to be missing... followed by the same for the opposite bound. stops
# sequences that begin properly but do not end so will be assumed to represent
# the bus travelling back to the garage. If in the linear search, the initial
# stop of the opposing bound is reached before the terminal stop of the current
# bound is found, the current sequence will be discarded and the search started
# anew for the opposing bound.
def construct_intermediate_run_product_csv(runs_csv_path, route_csv_paths):
  """
  Given a csv containing an time-ordered sequence of stops a bus traveled to
  or past, and the arrival time for each stop, extract instances of runs from
  initial stop to terminal stop
  """
  per_bound_stops_array_map = read_per_bound_route_csvs(route_csv_paths)

  northbound_stops = per_bound_stops_array_map['northbound']
  northbound_initial_stop_id = northbound_stops[0, 2]
  northbound_terminal_stop_id = northbound_stops[-1, 2]
  northbound_terminal_stop_sequence = northbound_stops[-1, -1]

  southbound_stops = per_bound_stops_array_map['southbound']
  southbound_initial_stop_id = southbound_stops[0, 2]
  southbound_terminal_stop_id = southbound_stops[-1, 2]
  southbound_terminal_stop_sequence = southbound_stops[-1, -1]

  route_id = southbound_stops[0, 0]
  route_name = southbound_stops[0, 1]

  # print('{}, {}, {}, {}'.format(
  #   northbound_initial_stop_id, northbound_terminal_stop_id,
  #   southbound_initial_stop_id, southbound_terminal_stop_id))

  run_stops_array = read_runs_csv(runs_csv_path)

  run_list = []

  previous_stop_sequence = None

  current_run_stops = None

  current_run = None

  for i in range(run_stops_array.shape[0]):
    current_stop = run_stops_array[i]
    current_stop_id = current_stop[0]
    
    if current_stop_id == northbound_initial_stop_id:
      #print('current_stop_id == northbound_initial_stop_id')
      current_run_stops = northbound_stops
      if i == 0 or previous_stop_sequence == southbound_terminal_stop_sequence:
        # print(
        #   'northbound_initial_stop_id: {}'.format(northbound_initial_stop_id))
        # if the previous 'current_run' was not closed and added to the list of
        # runs, then we abandon it here. how this impacts the representation of
        # driver experience is an open question
        current_run = IntermediateRun(
          route_id, route_name, northbound_stops[0], northbound_stops[-1],
          'northbound', vehicle_id=current_stop[2], start_time=current_stop[3])
      else:
        pass  # if not, we're in trouble! 
        # if != last southbound sequence_id but still in set of southbound ids,
        # then remove the most recently added run from the tail of the list,
        # under the assumption that a bus will always stop (e.g. for a break) at
        # the terminal stop. but since our data is perfect, worry about this
        # later. alternatively, in order to not
      index = np.squeeze(
        np.argwhere(current_run_stops[:, 2] == northbound_initial_stop_id))
      #print('index: {}'.format(index))
      previous_stop_sequence = current_run_stops[index, 5]
      #print('previous_stop_sequence: {}'.format(previous_stop_sequence))
    elif current_stop_id == northbound_terminal_stop_id:
      #print('current_stop_id == northbound_terminal_stop_id')
      # complete construction of the run most recently added to run_list
      index = np.squeeze(
        np.argwhere(current_run_stops[:, 2] == northbound_terminal_stop_id))
      #print('stop_sequence_index: {}'.format(index))
      current_stop_sequence = current_run_stops[index, 5]
      #print('current_stop_sequence: {}'.format(current_stop_sequence))
      #print('previous_stop_sequence: {}'.format(previous_stop_sequence))
      if current_stop_sequence > previous_stop_sequence:
        current_run.end_time = current_stop[6]
        # print('current_run.start_time: {}'.format(current_run.start_time))
        # print('current_run.end_time:   {}'.format(current_run.end_time))
        run_list.append(current_run)
      else:
        pass
      previous_stop_sequence = current_stop_sequence
    elif current_stop_id == southbound_initial_stop_id:
      #print('current_stop_id == southbound_initial_stop_id')
      current_run_stops = southbound_stops
      if i == 0 or previous_stop_sequence == northbound_terminal_stop_sequence:
        # print(
        #   'southbound_initial_stop_id: {}'.format(southbound_initial_stop_id))
        # if the previous 'current_run' was not closed and added to the list of
        # runs, then we abandon it here
        current_run = IntermediateRun(
          route_id, route_name, southbound_stops[0], southbound_stops[-1],
          'southbound', vehicle_id=current_stop[2], start_time=current_stop[3])
      else:
        pass
      index = np.squeeze(
        np.argwhere(current_run_stops[:, 2] == southbound_initial_stop_id))
      #print('index: {}'.format(index))
      previous_stop_sequence = current_run_stops[index, 5]
      #print('previous_stop_sequence: {}'.format(previous_stop_sequence))
    elif current_stop_id == southbound_terminal_stop_id:
      #print('current_stop_id == southbound_terminal_stop_id')
      # complete construction of the run most recently added to run_list
      index = np.squeeze(
        np.argwhere(current_run_stops[:, 2] == southbound_terminal_stop_id))
      #print('stop_sequence_index: {}'.format(index))
      current_stop_sequence = current_run_stops[index, 5]
      #print('current_stop_sequence: {}'.format(current_stop_sequence))
      #print('previous_stop_sequence: {}'.format(previous_stop_sequence))
      if current_stop_sequence > previous_stop_sequence:
        current_run.end_time = current_stop[6]
        # print('current_run.start_time: {}'.format(current_run.start_time))
        # print('current_run.end_time:   {}'.format(current_run.end_time))
        run_list.append(current_run)
      else:
        pass
      previous_stop_sequence = current_stop_sequence
    else:
      #print('otherwise')
      index = np.squeeze(
        np.argwhere(current_run_stops[:, 2] == current_stop_id))
      previous_stop_sequence = current_run_stops[index, 5]
      #print('previous_stop_sequence: {}'.format(previous_stop_sequence))

  return run_list

# OLD Algorithm
# create data_product_array
# read warnings CSV into warnings_array
# read schedule CSV into schedule_array
# identify set of dates among start_times in schedule CSV
# for each unique date
#   identify set of BusNumbers in schedule CSV
#   for each BusNumber
#     identify start_time-stop_time pairs on the current date
#     for each start_time-stop_time pair
#       identify set of warnings for which start_time <= Loc Time <= stop_time,
#       Vehicle Name == BusNumber
#       append to data_product_array a new list of [entire warning record]
#       concatenated with vehicle_id, stop_set_id, driver_id, tp_run_id,
#       RunName
# write data_product_array to intermediate_warning_product CSV

# NEW Algorithm
# given the warning CSV and the intermediate runs CSV, find the set of all
# warnings per run and append the run values to each warning record. This serves
# to 'prune' warnings that occurred outside of a run. Then, separately, append
# the driver id based on datetime.
def construct_intermediate_warning_product_csv(
  run_list, schedule_csv, warning_csv):
  """
  Given a Schedule CSV and a Warnings CSV, construct a single CSV product
  that pairs warnings with the driver id and vehicle id associated with the
  warning
  """
  warnings_array = read_warnings_csv(warning_csv)
  drivers_array = read_schedule_csv(schedule_csv)

  # collect the indices from which warnings have been assigned to a run
  # warnings that may have occurred at a time belonging to two consecutive runs
  # can be handled in isolation using the remaining zero values
  unassigned_warning_indices = np.ones((len(warnings_array),))

  # because runs resolve to the minute, not the second (like warnings) a warning
  # may be assigned to two runs when the start and end minute of the first and
  # second run, respectively, are equal. handle using the nearest lat/lon
  for run in run_list:
    run_warning_indices_start = np.nonzero(
      run.start_time < warnings_array[:, 0])
    # print('run_warning_indices_start: {}'.format(run_warning_indices_start))

    run_warning_indices_end = np.nonzero(
      warnings_array[:, 0] < run.end_time)
    # print('run_warning_indices_end: {}'.format(run_warning_indices_end))

    run_warning_indices = np.intersect1d(
      run_warning_indices_start, run_warning_indices_end)

    print('{}'.format(run))
    print('run_warning_indices: {}'.format(run_warning_indices))

    run.warning_list = warnings_array[run_warning_indices]

    driver_indices_start = np.nonzero(drivers_array[:, 3] <= run.start_time)
    print('driver_indices_start: {}'.format(driver_indices_start))
    driver_indices_end = np.nonzero(drivers_array[:, 4] >= run.end_time)
    print('driver_indices_end: {}'.format(driver_indices_end))

    driver_index = np.intersect1d(driver_indices_start, driver_indices_end)
    print('driver_index: {}'.format(driver_index))

    print(driver_index)

    assert len(driver_index) == 1

    driver_index = np.squeeze(driver_index)

    run.driver_id = drivers_array[driver_index, 2]
    print('run.driver_id: {}\n'.format(run.driver_id))

    unassigned_warning_indices[run_warning_indices] = 0
  print('unassigned_warning_indices: {}'.format(unassigned_warning_indices))
  #TODO: handle unassigned warnings

# read intermediate_warning_product CSV
# from warning CSV, read Loc Time and Vehicle Name
# use each record in the int_run_prod to extract a set of corresponding warnings
# that occurred during that run, and for each warning append the attributes of
# the run and write the resultant record to the final product output
def construct_final_warning_product_csv(intermediate_warning_product_csv,
                                        intermediate_run_product_csv):
  """
  Use the arrival/departure times of the initial/terminal stops to determine
  the direction of travel during a warning event, and the run number on which
  the event occurred, where run numbers are unique within a single day.
  """
  pass


if __name__ == '__main__':
  runs_path = \
    'C:/Users/franklin.abodo/Documents/NHTSA/LADOT/Data Integration Examples/' \
    'bus_number_15301_vehicle_id_324_route_DASH_B_date_2018.10.3_runs_clean.csv'

  route_path_tepmplate = \
    'C:/Users/franklin.abodo/Documents/NHTSA/LADOT/Data Integration Examples/' \
    'bus_number_15301_vehicle_id_324_route_DASH_B_date_2018.10.3_route_{}.csv'

  runs_array = construct_intermediate_run_product_csv(
    runs_path, {'northbound': route_path_tepmplate.format('northbound'),
                'southbound': route_path_tepmplate.format('southbound')})

  schedule_path = \
    'C:/Users/franklin.abodo/Documents/NHTSA/LADOT/Data Integration Examples/' \
    'bus_number_15301_vehicle_id_324_route_DASH_B_date_2018.10.3_schedule.csv'

  warnings_path = \
    'C:/Users/franklin.abodo/Documents/NHTSA/LADOT/Data Integration Examples/' \
    'bus_number_15301_vehicle_id_324_route_DASH_B_date_2018.10.3_warnings.csv'

  construct_intermediate_warning_product_csv(
    runs_array, schedule_path, warnings_path)

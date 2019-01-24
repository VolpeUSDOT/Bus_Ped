import argparse
import csv
import os.path
from datetime import datetime
import numpy as np
import pandas as pd
import win32com.client as pw  # for pywin read/write of xlsx files

#TODO add bus name to output as mapped from vehicle id
longitudinal_header = np.array([
  'Route Name', 'Route ID', 'Vehicle ID', 'Driver ID', 'Heading', 'Start Time',
  'End Time', 'ME - Pedestrian Collision Warning',
  'ME - Pedestrian In Range Warning', 'PCW-LF', 'PCW-LR', 'PCW-RR',
  'PDZ - Left Front', 'PDZ-LR', 'PDZ-R', 'Safety - Braking - Aggressive',
  'Safety - Braking - Dangerous'])

longitudinal_type = np.dtype([
  (longitudinal_header[0], np.unicode_, 6), (longitudinal_header[1], np.uint32),
  (longitudinal_header[2], np.uint32), (longitudinal_header[3], np.uint32),
  (longitudinal_header[4], np.unicode_, 10), (longitudinal_header[5], datetime),
  (longitudinal_header[6], datetime), (longitudinal_header[7], np.uint16),
  (longitudinal_header[8], np.uint16), (longitudinal_header[9], np.uint16),
  (longitudinal_header[10], np.uint16), (longitudinal_header[11], np.uint16),
  (longitudinal_header[12], np.uint16), (longitudinal_header[13], np.uint16),
  (longitudinal_header[14], np.uint16), (longitudinal_header[15], np.uint16),
  (longitudinal_header[16], np.uint16)])

hotspot_header = np.array([
  'Route Name', 'Route ID', 'Vehicle ID', 'Driver ID', 'Heading',
  'Loc Time', 'Warning Name', 'Latitude', 'Longitude'])

hotspot_type = np.dtype([
  (hotspot_header[0], np.unicode_, 6), (hotspot_header[1], np.uint32),
  (hotspot_header[2], np.uint32), (hotspot_header[3], np.uint32),
  (hotspot_header[4], np.unicode_, 10), (hotspot_header[5], datetime),
  (hotspot_header[6], np.unicode_, 34), (longitudinal_header[7], np.float64),
  (longitudinal_header[8], np.float64)])

warnings_header = longitudinal_header[7:]


class Run:
  def __init__(self, route_id, route_name, heading, initial_stop, terminal_stop,
               vehicle_id=None, driver_id=None, start_time=None, end_time=None,
               warnings=None):
    self.route_id = route_id
    self.route_name = route_name
    self.heading = heading
    self.initial_stop = initial_stop
    self.terminal_stop = terminal_stop
    self.vehicle_id = vehicle_id
    self.driver_id = driver_id
    self.start_time = start_time
    self.end_time = end_time
    self.warnings = warnings

  def __str__(self):
    return '[{}, {}, {}, {}, {}]'.format(
      self.route_id, self.route_name, self.heading, self.vehicle_id,
      self.driver_id, self.start_time, self.end_time)


def to_tuple(element):
  return np.array(tuple(element), dtype=hotspot_type)


def convert_stop_time_to_datetime(element):
  return datetime.strptime(element[0], '%m/%d/%Y %H:%M')


# we assume that the input format and data is perfect
def read_schedule_csv(array_csv):
  df = pd.read_csv(array_csv)

  array = np.concatenate((np.concatenate(
    (df.values[:, 1:4], df.values[:, 5:7]),
    axis=1), np.expand_dims(df.values[:, 11], 1)), axis=1)

  array[:, 3] = np.apply_along_axis(
    convert_stop_time_to_datetime, 1, np.expand_dims(array[:, 3], 1))

  array[:, 4] = np.apply_along_axis(
    convert_stop_time_to_datetime, 1, np.expand_dims(array[:, 4], 1))

  return array


# we assume that the input format and data is perfect
def read_runs_csv(array_csv):
  df = pd.read_csv(array_csv)

  array = np.concatenate((df.values[:, 0:3], df.values[:, 4:10]), axis=1)

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


def convert_vehicle_name_to_bus_number(element):
  return int(element[0].split()[-1])


# we assume that the input format and data is perfect
def read_warnings_csv(warnings_csv):
  df = pd.read_csv(warnings_csv)
  array = np.concatenate((df.values[:, :2], df.values[:, 3:]), axis=1)

  array[:, 0] = np.apply_along_axis(
    convert_loc_time_to_datetime, 1, np.expand_dims(array[:, 0], 1))

  array[:, 1] = np.apply_along_axis(
    convert_vehicle_name_to_bus_number, 1, np.expand_dims(array[:, 1], 1))

  return array


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
def construct_run_list(runs_csv_path, route_csv_paths):
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

  run_stops_array = read_runs_csv(runs_csv_path)

  run_list = []

  previous_stop_sequence = None

  current_run_stops = None

  current_run = None

  for i in range(run_stops_array.shape[0]):
    current_stop = run_stops_array[i]
    current_stop_id = current_stop[0]

    if current_stop_id == northbound_initial_stop_id:

      current_run_stops = northbound_stops
      if i == 0 or previous_stop_sequence == southbound_terminal_stop_sequence:
        # if the previous 'current_run' was not closed and added to the list of
        # runs, then we abandon it here. how this impacts the representation of
        # driver experience is an open question
        current_run = Run(
          route_id, route_name, 'northbound', northbound_stops[0],
          northbound_stops[-1], vehicle_id=current_stop[2],
          start_time=current_stop[3])
      else:
        pass  # if not, we're in trouble!
        # if != last southbound sequence_id but still in set of southbound ids,
        # then remove the most recently added run from the tail of the list,
        # under the assumption that a bus will always stop (e.g. for a break) at
        # the terminal stop. but since our data is perfect, worry about this
        # later. alternatively, in order to not
      index = np.squeeze(
        np.argwhere(current_run_stops[:, 2] == northbound_initial_stop_id))

      previous_stop_sequence = current_run_stops[index, 5]

    elif current_stop_id == northbound_terminal_stop_id:
      # complete construction of the run most recently added to run_list
      index = np.squeeze(
        np.argwhere(current_run_stops[:, 2] == northbound_terminal_stop_id))

      current_stop_sequence = current_run_stops[index, 5]

      if current_stop_sequence > previous_stop_sequence:
        current_run.end_time = current_stop[6]

        run_list.append(current_run)
      else:
        pass
      previous_stop_sequence = current_stop_sequence
    elif current_stop_id == southbound_initial_stop_id:
      current_run_stops = southbound_stops
      if i == 0 or previous_stop_sequence == northbound_terminal_stop_sequence:
        # if the previous 'current_run' was not closed and added to the list of
        # runs, then we abandon it here
        current_run = Run(
          route_id, route_name, 'southbound', southbound_stops[0],
          southbound_stops[-1], vehicle_id=current_stop[2],
          start_time=current_stop[3])
      else:
        pass
      index = np.squeeze(
        np.argwhere(current_run_stops[:, 2] == southbound_initial_stop_id))

      previous_stop_sequence = current_run_stops[index, 5]

    elif current_stop_id == southbound_terminal_stop_id:
      index = np.squeeze(
        np.argwhere(current_run_stops[:, 2] == southbound_terminal_stop_id))

      current_stop_sequence = current_run_stops[index, 5]

      if current_stop_sequence > previous_stop_sequence:
        current_run.end_time = current_stop[6]

        run_list.append(current_run)
      else:
        pass
      previous_stop_sequence = current_stop_sequence
    else:
      index = np.squeeze(
        np.argwhere(current_run_stops[:, 2] == current_stop_id))
      previous_stop_sequence = current_run_stops[index, 5]

  return run_list


def assign_warnings_to_runs(run_list, schedule_csv, warning_csv):
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

    run_warning_indices_end = np.nonzero(warnings_array[:, 0] < run.end_time)

    run_warning_indices = np.intersect1d(
      run_warning_indices_start, run_warning_indices_end)

    run.warnings = warnings_array[run_warning_indices]

    driver_indices_start = np.nonzero(drivers_array[:, 3] <= run.start_time)

    driver_indices_end = np.nonzero(drivers_array[:, 4] >= run.end_time)

    driver_index = np.intersect1d(driver_indices_start, driver_indices_end)

    assert len(driver_index) == 1

    driver_index = np.squeeze(driver_index)

    run.driver_id = drivers_array[driver_index, 2]

    unassigned_warning_indices[run_warning_indices] = 0

  # TODO: handle unassigned warnings
  return run_list


# given the warning CSV and the intermediate runs CSV, find the set of all
# warnings per run and append the run values to each warning record. This serves
# to 'prune' warnings that occurred outside of a run. Then, separately, append
# the driver id based on datetime.
def construct_longitudinal_study_data_product(run_list):
  output_data = np.ndarray((len(run_list),), dtype=longitudinal_type)

  # run being aggregated
  for i in range(len(run_list)):
    run = run_list[i]

    run_data = np.array([[
      run.route_name, run.route_id, run.vehicle_id, run.driver_id, run.heading,
      run.start_time, run.end_time]])

    unique_warnings, counts = np.unique(run.warnings[:, 2], return_counts=True)

    warning_data = np.zeros((1, warnings_header.shape[0]))

    for j in range(unique_warnings.shape[0]):
      index = np.nonzero(warnings_header == unique_warnings[j])

      if len(index) > 0:
        assert len(index) == 1
        warning_data[0, index] = counts[j]

    run_data = np.squeeze(np.concatenate((run_data, warning_data), axis=1))

    output_data[i] = tuple(run_data)

  print('output_data: {}'.format(output_data))

  with open(os.path.join(r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data\Data Integration Examples',
            'longitudinal_example.csv'),
            mode='w', newline='') as output_file:
    csv_writer = csv.writer(output_file)
    csv_writer.writerow(longitudinal_header)
    csv_writer.writerows(output_data)


def construct_hotspot_analysis_data_product(run_list):
  """

  """
  output_data = np.ndarray(
    (sum([run.warnings.shape[0] for run in run_list]),), dtype=hotspot_type)

  index = 0

  for run in run_list:
    if run.warnings.shape[0] > 0:
      run_data = np.tile([run.route_name, run.route_id, run.vehicle_id,
                          run.driver_id, run.heading],
                         (run.warnings.shape[0], 1))

      warning_data = np.concatenate((np.expand_dims(
        run.warnings[:, 0], axis=1), run.warnings[:, 2:]), axis=1)

      output_data[index:index + run.warnings.shape[0]] = np.apply_along_axis(
        to_tuple, 1, np.concatenate((run_data, warning_data), axis=1))

      index += run.warnings.shape[0]

  print('output_data: {}'.format(output_data))

  with open(os.path.join(r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data\Data Integration Examples',
            'hotspot_example.csv'),
            mode='w', newline='') as output_file:
    csv_writer = csv.writer(output_file)
    csv_writer.writerow(hotspot_header)
    csv_writer.writerows(output_data)


if __name__ == '__main__':
  root_path = r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data\Data Integration Examples'
  runs_path = os.path.join(root_path, 'bus_number_15301_vehicle_id_324_route_DASH_B_date_2018.10.3_runs_clean.csv')

  route_path_tepmplate = os.path.join(root_path, 'bus_number_15301_vehicle_id_324_route_DASH_B_date_2018.10.3_route_{}.csv')

  run_list = construct_run_list(
    runs_path, {'northbound': route_path_tepmplate.format('northbound'),
                'southbound': route_path_tepmplate.format('southbound')})

  schedule_path = os.path.join(root_path, 'bus_number_15301_vehicle_id_324_route_DASH_B_date_2018.10.3_schedule.csv')

  warnings_path = os.path.join(root_path, 'bus_number_15301_vehicle_id_324_route_DASH_B_date_2018.10.3_warnings.csv')

  run_list = assign_warnings_to_runs(run_list, schedule_path, warnings_path)

  construct_longitudinal_study_data_product(run_list)
  construct_hotspot_analysis_data_product(run_list)
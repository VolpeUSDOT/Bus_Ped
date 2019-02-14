import argparse
from datetime import datetime
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

# This script creates or replaces two tables in the database at the supplied
# path that contain 'clean' subsets of LADOT DASH run data, where a clean run is
# defined as having a pair of 'terminal' stops with a sequence of all northbound
# stops followed by all southbound stops (or vice versa) in between, and having
# a number of stop events no greater than the total number of stops that
# constitute a round trip on the route. A terminal stop is a stop where drivers
# transition their shifts.
#
# TODO: resolve issues that prevent all stop events from being included in the
# data product, e.g. when buses return to a depo from a stop other than the
# terminal, or when a driver running multiple contiguous rounds trips in a
# single shift does not stop at the terminal between two bounds.
#
# The hotspot_data_product table contains per-warning records for the purpose of
# hotspot analysis and the longitudinal_data_product table contains per-run
# records, with warnings aggegated into counts for the purpose of longitudinal
# analysis.
#
# Data product construction is performed in three phases. First, individual runs
# are identified in construct_run_list(), then corresponding warnings are
# assigned to each run based on a time range and a vehicle id in
# assign_warnings_to_runs(), and finally either a hotspot or a longitudinal data
# product is constructed given the runs and their warnings in
# construct_hotspot_data_product() or construct_longitudinal_data_product()
#
# TODO: log print statements
# TODO: only db read stop events in the date range across driver schedules

# define hostpot table column names and a custom data type fo organizing data
# into records
hotspot_header = np.array([
  'route_name', 'route_id', 'heading', 'driver_id', 'vehicle_id', 'bus_number',
  'loc_time', 'warning_name', 'latitude', 'longitude'])

hotspot_type = np.dtype([
  (hotspot_header[0], np.unicode_, 6), (hotspot_header[1], np.uint32),
  (hotspot_header[2], np.unicode_, 10), (hotspot_header[3], np.uint32),
  (hotspot_header[4], np.uint32), (hotspot_header[5], np.uint32),
  (hotspot_header[6], datetime), (hotspot_header[7], np.unicode_, 34),
  (hotspot_header[8], np.float64), (hotspot_header[9], np.float64)])

# define longitudinal table column names and a custom data type fo organizing
# data into records
longitudinal_header = np.array([
  'route_name', 'route_id', 'heading', 'driver_id', 'vehicle_id', 'bus_number',
  'start_time', 'end_time', 'ME - Pedestrian Collision Warning',
  'ME - Pedestrian In Range Warning', 'PCW-LF', 'PCW-LR', 'PCW-RR',
  'PDZ - Left Front', 'PDZ-LR', 'PDZ-R', 'Safety - Braking - Aggressive',
  'Safety - Braking - Dangerous'])

longitudinal_type = np.dtype([
  (longitudinal_header[0], np.unicode_, 6), (longitudinal_header[1], np.uint32),
  (longitudinal_header[2], np.unicode_, 10), (longitudinal_header[3], np.uint32),
  (longitudinal_header[4], np.uint32), (longitudinal_header[5], np.uint32),
  (longitudinal_header[6], datetime),
  (longitudinal_header[7], datetime), (longitudinal_header[8], np.uint16),
  (longitudinal_header[9], np.uint16), (longitudinal_header[10], np.uint16),
  (longitudinal_header[11], np.uint16), (longitudinal_header[12], np.uint16),
  (longitudinal_header[13], np.uint16), (longitudinal_header[14], np.uint16),
  (longitudinal_header[15], np.uint16), (longitudinal_header[16], np.uint16),
  (longitudinal_header[17], np.uint16)])

# a separate collection of warning headers will be used to first create warning
# count data before concatenating them with run data to form longitudinal
# records
warnings_header = longitudinal_header[8:]


# a Run object is used to organize an individual run's properties together with
# a collection of warnings that may vary in length from run to run
class Run:
  def __init__(self, route_name, route_id, heading, vehicle_id,
               start_time, end_time, driver_id=None, bus_number=None, warnings=None):
    self.route_name = route_name
    self.route_id = route_id
    self.heading = heading
    self.vehicle_id = vehicle_id
    self.start_time = start_time
    self.end_time = end_time
    self.driver_id = driver_id
    self.bus_number = bus_number
    self.warnings = warnings


# numpy arrays of custom dtype expect elements to be tuples. Because
# longitudinal records are created in batches, organization of data into a tuple
# must be applied row-wise across the batch dimension
def to_tuple(element):
  return np.array(tuple(element), dtype=hotspot_type)


def construct_run_list(route_stops, stop_times):
  """
  Given a time-ordered sequence of stops a bus traveled to or past, and the
  arrival time for each stop, extract instances of round trips (between the
  departure from a terminal to the arrival at that same stop. Records for which
  consecutive terminal stops have an unreasonable number of intermediate stops
  (e.g. more than the total number of stops that constitute a route) will be
  ignored.
  """
  run_list = []

  terminal_stop_id = route_stops[
    route_stops['is_terminal'] == True]['stop_id'].squeeze()
  # print('terminal_stop_id: {}'.format(terminal_stop_id))

  # assume that the stop_times have been sorted by arrived_at then departed_at
  terminal_stop_indices = stop_times[
    stop_times['stop_id'] == terminal_stop_id].index.values
  # print('terminal_stop_indices: {}'.format(terminal_stop_indices))

  northbound_stop_ids = route_stops[
    route_stops.heading == 'N']['stop_id'].values
  northbound_stop_ids = northbound_stop_ids.astype(np.uint32)
  # print('northbound_stop_ids: {}'.format(northbound_stop_ids))

  southbound_stop_ids = route_stops[
    route_stops.heading == 'S']['stop_id'].values
  southbound_stop_ids = southbound_stop_ids.astype(np.uint32)
  # print('southbound_stop_ids: {}'.format(southbound_stop_ids))
  # exit()
  def is_northbound(stop_id):
    # print('n_stop_id: {}'.format(stop_id))
    return True if stop_id in northbound_stop_ids else False

  def is_southbound(stop_id):
    # print('s_stop_id: {}'.format(southbound_stop_ids))
    return True if stop_id in southbound_stop_ids else False

  for i in range(len(terminal_stop_indices) - 1):
    round_trip_stop_times = stop_times.loc[
                            terminal_stop_indices[i]:terminal_stop_indices[i+1]]
    # print('round_trip_stop range: [{}, {}], size: {}'.format(
    #   terminal_stop_indices[i], terminal_stop_indices[i + 1],
    #   round_trip_stop_times.shape[0]))
    # ignore ranges that are longer than a single round trip
    if round_trip_stop_times.shape[0] <= route_stops.shape[0]:
      #confirm that the sequence of runs divides cleanly across the two bounds
      are_northbound = round_trip_stop_times['stop_id'].apply(is_northbound)
      # print('are_northbound: {}'.format(are_northbound))

      are_southbound = round_trip_stop_times['stop_id'].apply(is_southbound)
      # print('are_southbound: {}'.format(are_southbound))

      are_equal = are_northbound == are_southbound
      # print('are_equal: {}'.format(are_equal))

      if not are_equal.any():
        northbound_indices = are_northbound.iloc[1:-1][
          are_northbound.iloc[1:-1] == True].index
        # print('northbound_indices:\n{}'.format(northbound_indices))
        southbound_indices = are_southbound.iloc[1:-1][
          are_southbound.iloc[1:-1] == True].index
        # print('southbound_indices:\n{}'.format(southbound_indices))
        # assume argwhere will preserve the index ordering
        if southbound_indices.shape[0] > 0 and northbound_indices.shape[0] > 0:
          route_id = round_trip_stop_times.iloc[0]['route_id']
          route_name = route_stops.iloc[0]['route_name']
          vehicle_id = round_trip_stop_times.iloc[0]['vehicle_id']

          # in this round trip, the northbound trip precedes the southbound trip
          if southbound_indices[0] > northbound_indices[-1]:
            # the southbound trip
            start_time = round_trip_stop_times.iloc[0]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.loc[
              northbound_indices[-1]]['arrived_at']
            # print('end_time: {}'.format(end_time))
            run_list.append(Run(
              route_name, route_id, 'N', vehicle_id, start_time, end_time))

            start_time = round_trip_stop_times.loc[
              northbound_indices[-1]]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.iloc[-1]['arrived_at']
            # print('end_time: {}'.format(end_time))

            run_list.append(Run(
              route_name, route_id, 'S', vehicle_id, start_time, end_time))
          elif northbound_indices[0] > southbound_indices[-1]:
            start_time = round_trip_stop_times.iloc[0]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.loc[
              southbound_indices[-1]]['arrived_at']
            # print('end_time: {}'.format(end_time))

            run_list.append(Run(
              route_name, route_id, 'S', vehicle_id, start_time, end_time))

            start_time = round_trip_stop_times.loc[
              southbound_indices[-1]]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.iloc[-1]['arrived_at']
            # print('end_time: {}'.format(end_time))

            run_list.append(Run(
              route_name, route_id, 'N', vehicle_id, start_time, end_time))

  return run_list


def assign_warnings_to_runs(
  route_stop_df, stop_time_df, vehicle_assignment_df, warning_df):
  """
  Given four pandas data frames representing warning events, route stops,
  stop events and driver schedules, construct a list of individual route runs,
  assign warning events that occurred during each run to that run, then return
  the complete list.
  """
  global_run_list = []
  # print('vehicle_assignment_df:\n{}'.format(vehicle_assignment_df.describe()))
  # stop_time_df.sort_values(['arrived_at', 'departed_at'], inplace=True)
  # stop_time_df.set_index(pd.RangeIndex(stop_time_df.shape[0]), inplace=True)

  relevant_route_ids = stop_time_df['route_id'].unique()
  #since DASH A routes are not in teh DB yet...
  available_route_ids = route_stop_df['route_id'].unique()

  for route_id in relevant_route_ids:
    if route_id in available_route_ids:
      # collect all driver assignments for the given route for all time
      vehicles_that_ran_route = vehicle_assignment_df[
        vehicle_assignment_df['route_id'] == route_id]
      # print('relevant_vehicle_assignments:\n{}'.format(relevant_vehicle_assignments))

      # identify unique set of vehicle ids for all time
      unique_vehicle_ids = vehicles_that_ran_route['vehicle_id'].unique()
      # print('unique_vehicle_ids:\n{}  '.format(unique_vehicle_ids))

      for vehicle_id in unique_vehicle_ids:
        relevant_vehicle_assignments = vehicles_that_ran_route[
          vehicles_that_ran_route['vehicle_id'] == vehicle_id]

        relevant_driver_ids = relevant_vehicle_assignments['driver_id'].unique()

        for driver_id in relevant_driver_ids:
          driver_assignments = relevant_vehicle_assignments[
            relevant_vehicle_assignments['driver_id'] == driver_id]

          for i in range(driver_assignments.shape[0]):
            driver_start_time = driver_assignments.iloc[i].start_time
            driver_end_time = driver_assignments.iloc[i].end_time

            # here we assume that any bus on the given route for the given
            # driver during a given run (of multiple trips) will not switch to
            # a different route and then switch back.

            # although it is possible for some stops to be included that follow
            # the driver's run start time but precede the route's initial stop,
            # warnings during that interval will be ignored and only those
            # occurring after the first stop departure will be included
            driver_stop_times = stop_time_df.query(
              'route_id == @route_id & '
              'vehicle_id == @vehicle_id & '
              'departed_at > @driver_start_time & '
              'arrived_at < @driver_end_time')

            driver_stop_times = driver_stop_times.sort_values(
              ['arrived_at', 'departed_at'])

            driver_stop_times.set_index(
              pd.RangeIndex(driver_stop_times.shape[0]), inplace=True)

            print('route: {}, vehicle: {}, driver: {}, start_time: {}, '
                  'end_time: {}'.format(route_id, vehicle_id, driver_id,
                                        driver_start_time, driver_end_time))

            # print('route: {}, vehicle: {}, driver: {}, start_time: {}, '
            #       'end_time: {}, stops:\n{}'.format(
            #   route_id, vehicle_id, driver_id, driver_start_time,
            #   driver_end_time, driver_stop_times.describe()))

            # collect set of stops for the given route
            route_stops = route_stop_df[route_stop_df['route_id'] == route_id]
            route_stops = route_stops.sort_values(['heading', 'sequence'])
            route_stops.set_index(pd.RangeIndex(route_stops.shape[0]),
                                  inplace=True)
            # print('route {} stops:\n{}'.format(route_id, route_stops.describe()))

            route_run_list = construct_run_list(route_stops, driver_stop_times)
            print('found {} route runs'.format(len(route_run_list)))

            driver_bus_number = driver_assignments.iloc[i].bus_number

            for run in route_run_list:
              run.driver_id = driver_id
              run.bus_number = driver_bus_number
              # print('run_start_time: {}, run_end_time: {}'.format(run_start_time, run_end_time))
              run.warnings = warning_df.query(
                'bus_number == @run.bus_number & '
                'loc_time > @run.start_time & '
                'loc_time <= @run.end_time')

              print('run warnings: {}'.format(run.warnings))

            global_run_list.extend(route_run_list)

  # TODO: handle unassigned warnings
  return global_run_list


def construct_longitudinal_data_product(run_list):
  """Given a list of Run objects with warnings assigned, create longitudinal
  records and return them as a numpy array """
  output_data = np.ndarray((len(run_list),), dtype=longitudinal_type)

  # run being aggregated
  for i in range(len(run_list)):
    run = run_list[i]

    run_data = np.array([[
      run.route_name, run.route_id, run.heading, run.driver_id, run.vehicle_id,
      run.bus_number, run.start_time, run.end_time]])

    unique_warnings, counts = np.unique(
      run.warnings.loc[:, 'warning_name'].values, return_counts=True)

    warning_data = np.zeros((1, warnings_header.shape[0]))

    for j in range(unique_warnings.shape[0]):
      index = np.nonzero(warnings_header == unique_warnings[j])

      if len(index) > 0:
        assert len(index) == 1
        warning_data[0, index] = counts[j]

    run_data = np.squeeze(np.concatenate((run_data, warning_data), axis=1))

    output_data[i] = tuple(run_data)

  output_data = pd.DataFrame(output_data)

  print('output_data: {}'.format(output_data.describe()))

  return output_data


def construct_hotspot_data_product(run_list):
  output_data = np.ndarray(
    (sum([run.warnings.shape[0] for run in run_list]),), dtype=hotspot_type)

  index = 0

  for run in run_list:
    if run.warnings.shape[0] > 0:
      warning_data = run.warnings.loc[:, ['loc_time', 'warning_name',
                                          'latitude', 'longitude']].values

      run_data = np.tile([
        run.route_name, run.route_id, run.heading, run.driver_id,
        run.vehicle_id, run.bus_number], (warning_data.shape[0], 1))

      output_data[index:index + warning_data.shape[0]] = np.apply_along_axis(
        to_tuple, 1, np.concatenate((run_data, warning_data), axis=1))

      index += warning_data.shape[0]

  output_data = pd.DataFrame(output_data)

  print('output_data: {}'.format(output_data.describe()))

  return output_data


if __name__ == '__main__':
  parser = argparse.ArgumentParser()

  parser.add_argument('--db_path', default='/ituran_synchromatics_data.sqlite')
  parser.add_argument('--route_stop_table_name', default='route_stop')
  parser.add_argument('--stop_event_table_name', default='stop_time')
  parser.add_argument('--driver_schedule_table_name',
                      default='vehicle_assignment')
  parser.add_argument('--warning_table_name', default='warning')
  parser.add_argument('--hotspot_record_table_name',
                      default='hotspot_data_product')
  parser.add_argument('--longitudinal_record_table_name',
                      default='longitudinal_data_product')

  args = parser.parse_args()

  db_path = 'sqlite://' + args.db_path

  db = create_engine(db_path)

  route_stop_df = pd.read_sql_table(args.route_stop_table_name, db)
  stop_time_df = pd.read_sql_table(args.stop_event_table_name, db)
  vehicle_assignment_df = pd.read_sql_table(args.driver_schedule_table_name, db)
  warning_df = pd.read_sql_table(args.warning_table_name, db)

  run_list = assign_warnings_to_runs(
    route_stop_df, stop_time_df, vehicle_assignment_df, warning_df)
  print('found {} total runs'.format(len(run_list)))

  longitudinal_data = construct_longitudinal_data_product(run_list)
  hotspot_data = construct_hotspot_data_product(run_list)

  longitudinal_data.to_sql(args.longitudinal_record_table_name, db,
                           if_exists='replace', chunksize=1000000, index=False)
  hotspot_data.to_sql(args.hotspot_record_table_name, db, if_exists='replace',
                      chunksize=1000000, index=False)
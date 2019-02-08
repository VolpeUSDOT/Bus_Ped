import argparse
from datetime import datetime
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

hotspot_header = np.array([
  'route_name', 'route_id', 'heading', 'driver_id', 'vehicle_id', 'bus_number',
  'loc_time', 'warning_name', 'latitude', 'longitude'])

hotspot_type = np.dtype([
  (hotspot_header[0], np.unicode_, 6), (hotspot_header[1], np.uint32),
  (hotspot_header[2], np.unicode_, 10), (hotspot_header[3], np.uint32),
  (hotspot_header[4], np.uint32), (hotspot_header[5], np.uint32),
  (hotspot_header[6], datetime), (hotspot_header[7], np.unicode_, 34),
  (hotspot_header[8], np.float64), (hotspot_header[9], np.float64)])

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

warnings_header = longitudinal_header[8:]


class Run:
  def __init__(self, route_name, route_id, heading, driver_id, vehicle_id,
               start_time, end_time, bus_number=None, warnings=None):
    self.route_name = route_name
    self.route_id = route_id
    self.heading = heading
    self.driver_id = driver_id
    self.vehicle_id = vehicle_id
    self.start_time = start_time
    self.end_time = end_time
    self.bus_number = bus_number
    self.warnings = warnings


def to_tuple(element):
  return np.array(tuple(element), dtype=hotspot_type)


def construct_run_list(route_stops, stop_times):
  """
  Given a csv containing an time-ordered sequence of stops a bus traveled to
  or past, and the arrival time for each stop, extract instances of runs from
  initial stop to terminal stop
  """
  run_list = []
  # per_bound_stops_array_map = read_per_bound_routes_from_db(db)
  terminal_stop_id = route_stops[
    route_stops.is_terminal == True]['stop_id'].squeeze()
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
    round_trip_stop_times = stop_times.loc[terminal_stop_indices[i]:
                                           terminal_stop_indices[i+1]]
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
          driver_id = round_trip_stop_times.iloc[0]['vehicle_id']

          # in this round trip, the northbound trip precedes the southbound trip
          if southbound_indices[0] > northbound_indices[-1]:
            # the southbound trip
            start_time = round_trip_stop_times.iloc[0]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.loc[
              northbound_indices[-1]]['arrived_at']
            # print('end_time: {}'.format(end_time))
            run_list.append(Run(route_name, route_id, 'S', driver_id,
                                vehicle_id, start_time, end_time))

            start_time = round_trip_stop_times.loc[
              northbound_indices[-1]]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.iloc[-1]['arrived_at']
            # print('end_time: {}'.format(end_time))

            run_list.append(Run(route_name, route_id, 'S', driver_id,
                                vehicle_id, start_time, end_time))
          elif northbound_indices[0] > southbound_indices[-1]:
            start_time = round_trip_stop_times.iloc[0]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.loc[
              northbound_indices[0]]['arrived_at']
            # print('end_time: {}'.format(end_time))

            run_list.append(Run(route_name, route_id, 'S', driver_id,
                                vehicle_id, start_time, end_time))

            start_time = round_trip_stop_times.loc[
              northbound_indices[0]]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.iloc[-1]['arrived_at']
            # print('end_time: {}'.format(end_time))

            run_list.append(Run(route_name, route_id, 'N', driver_id,
                                vehicle_id, start_time, end_time))

  return run_list


def assign_warnings_to_runs(db):
  """
    Given a Schedule CSV and a Warnings CSV, construct a single CSV product
    that pairs warnings with the driver_id and vehicle_id associated with the
    warning
    """
  # warning_df = pd.read_sql_table('warning', db)
  global_run_list = []

  route_stop_df = pd.read_sql_table('route_stop', db)
  stop_time_df = pd.read_sql_table('stop_time', db)
  vehicle_assignment_df = pd.read_sql_table('vehicle_assignment', db)
  warning_df = pd.read_sql_table('warning', db)
  # print('vehicle_assignment_df:\n{}'.format(vehicle_assignment_df.describe()))
  # stop_time_df.sort_values(['arrived_at', 'departed_at'], inplace=True)
  # stop_time_df.set_index(pd.RangeIndex(stop_time_df.shape[0]), inplace=True)

  relevant_route_ids = stop_time_df['route_id'].unique()
  #since DASH A routes are not in teh DB yet...
  available_route_ids = route_stop_df['route_id'].unique()

  for route_id in relevant_route_ids:
    if route_id in available_route_ids:
      route_stops = route_stop_df[route_stop_df.route_id == route_id]
      route_stops = route_stops.sort_values(['heading', 'sequence'])
      route_stops.set_index(pd.RangeIndex(route_stops.shape[0]), inplace=True)
      # print('route {} stops:\n{}'.format(route_id, route_stops.describe()))

      route_vehicle_assignments = vehicle_assignment_df[
        vehicle_assignment_df.route_id == route_id]
      # print('relevant_vehicle_assignments:\n{}'.format(relevant_vehicle_assignments))

      relevant_vehicle_ids = route_vehicle_assignments['vehicle_id'].unique()
      # print('relevant_vehicle_ids:\n{}'.format(relevant_vehicle_ids))

      for vehicle_id in relevant_vehicle_ids:
        relevant_vehicle_assignments = route_vehicle_assignments[
          route_vehicle_assignments['vehicle_id'] == vehicle_id]

        relevant_driver_ids = relevant_vehicle_assignments['driver_id'].unique()

        for driver_id in relevant_driver_ids:
          driver_assignments = relevant_vehicle_assignments[
            relevant_vehicle_assignments['driver_id'] == driver_id]

          for i in range(driver_assignments.shape[0]):
            driver_start_time = driver_assignments.iloc[i]['start_time']
            driver_end_time = driver_assignments.iloc[i]['end_time']

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

            route_run_list = construct_run_list(route_stops, driver_stop_times)
            print('found {} route runs'.format(len(route_run_list)))

            driver_bus_number = driver_assignments.iloc[i]['bus_number']

            for run in route_run_list:
              run.bus_number = driver_bus_number
              # print('run_start_time: {}, run_end_time: {}'.format(run_start_time, run_end_time))
              run.warnings = warning_df.query(
                'bus_number == @run.bus_number & '
                'loc_time >= @run.start_time & '
                'loc_time <= @run.end_time')

              print('run warnings: {}'.format(run.warnings))

            global_run_list.extend(route_run_list)

  # # TODO: handle unassigned warnings
  return global_run_list


# given the warning CSV and the intermediate runs CSV, find the set of all
# warnings per run and append the run values to each warning record. This serves
# to 'prune' warnings that occurred outside of a run. Then, separately, append
# the driver_id based on datetime.
def construct_longitudinal_data_product(run_list):
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

  output_data.to_sql('longitudinal_data_product', db, if_exists='replace',
                     chunksize=1000000, index=False)


def construct_hotspot_data_product(run_list):
  """

  """
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

  output_data.to_sql('hotspot_data_product', db, if_exists='replace',
                     chunksize=1000000, index=False)

if __name__ == '__main__':
  db_path = 'sqlite:///ituran_synchromatics_data.sqlite'

  db = create_engine(db_path)

  run_list = assign_warnings_to_runs(db)
  print('found {} total runs'.format(len(run_list)))

  construct_longitudinal_data_product(run_list)
  construct_hotspot_data_product(run_list)
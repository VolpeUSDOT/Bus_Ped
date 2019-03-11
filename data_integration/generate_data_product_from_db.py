import argparse
from datetime import datetime
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

# This script creates or replaces two tables in the database at the supplied
# path that contain 'clean' subsets of LADOT DASH trip data, where a clean trip is
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
# hotspot analysis and the longitudinal_data_product table contains per-trip
# records, with warnings aggegated into counts for the purpose of longitudinal
# analysis.
#
# Data product construction is performed in three phases. First, individual trips
# are identified in construct_trip_list(), then corresponding warnings are
# assigned to each trip based on a time range and a vehicle id in
# assign_warnings_to_trips(), and finally either a hotspot or a longitudinal data
# product is constructed given the trips and their warnings in
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
# count data before concatenating them with trip data to form longitudinal
# records
warnings_header = longitudinal_header[8:]

valid_trip_count = 0
invalid_trip_count = 0
pseudo_invalid_trip_count = 0
trips_with_no_warnings = 0

# a Run object is used to organize an individual trip's properties together with
# a collection of warnings that may vary in length from trip to trip
class Trip:
  def __init__(self, route_name, route_id, heading, vehicle_id, start_time,
               end_time, stop_count, driver_id=None, bus_number=None, warnings=None):
    self.route_name = route_name
    self.route_id = route_id
    self.heading = heading
    self.vehicle_id = vehicle_id
    self.start_time = start_time
    self.end_time = end_time
    self.driver_id = driver_id
    self.bus_number = bus_number
    self.warnings = warnings
    self.stop_count = stop_count


# numpy arrays of custom dtype expect elements to be tuples. Because
# longitudinal records are created in batches, organization of data into a tuple
# must be applied row-wise across the batch dimension
def to_tuple(element):
  return np.array(tuple(element), dtype=hotspot_type)


def construct_trip_list(route_stops, stop_times):
  """
  Given a time-ordered sequence of stops a bus traveled to or past, and the
  arrival time for each stop, extract instances of round trips (between the
  departure from a terminal to the arrival at that same stop. Records for which
  consecutive terminal stops have an unreasonable number of intermediate stops
  (e.g. more than the total number of stops that constitute a route) will be
  ignored.
  """
  global valid_trip_count
  global invalid_trip_count
  global pseudo_invalid_trip_count
  global trips_with_no_warnings

  trip_list = []
  # print('stop_times: {}'.format(stop_times))

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

  def is_northbound(stop_id):
    # print('n_stop_id: {}'.format(stop_id))
    return True if stop_id in northbound_stop_ids else False

  def is_southbound(stop_id):
    # print('s_stop_id: {}'.format(southbound_stop_ids))
    return True if stop_id in southbound_stop_ids else False

  # for i in range(len(terminal_stop_indices)):
  for i in [-1] + list(range(len(terminal_stop_indices))):
    # treat any stops preceding the first terminal as a partial trip
    if i == -1:
      try:
        round_trip_stop_times = \
          stop_times.loc[stop_times.index.values[0]:terminal_stop_indices[0]]
        # print('{} stop times found before first terminal'.format(
        #   round_trip_stop_times.shape[0]))
      except:
        continue
    # since the last trip may not end at the terminal, grab all stops after
    # the last terminal. If the last trip truly did end at the terminal, the
    # below code should branch out appropriately
    elif i == len(terminal_stop_indices) - 1:
      try:
        round_trip_stop_times = \
          stop_times.loc[terminal_stop_indices[i]:stop_times.index.values[-1]]
        # print('{} stop times found after last terminal'.format(
        #   round_trip_stop_times.shape[0]))
      except:
        continue
    else:
      round_trip_stop_times = \
        stop_times.loc[terminal_stop_indices[i]:terminal_stop_indices[i+1]]
      # print('round_trip_stop_times_range: ({}, {})'.format(
      #   terminal_stop_indices[i], terminal_stop_indices[i+1]))

    # ignore ranges that are less than 3 stops long as these are probably
    # sequences of multiple records representing a single event
    if 2 <= round_trip_stop_times.shape[0]:  # <= route_stops.shape[0] * 1:#
      #confirm that the sequence of trips divides cleanly across the two bounds
      are_northbound = round_trip_stop_times['stop_id'].apply(is_northbound)
      # print('are_northbound: {}'.format(are_northbound.values))

      are_southbound = round_trip_stop_times['stop_id'].apply(is_southbound)
      # print('are_southbound: {}'.format(are_southbound.values))

      are_equal = are_northbound == are_southbound
      # print('are_equal: {}'.format(are_equal.values))

      if not are_equal.any():
        # ignore the 0th stop since the southbound terminal may precede an entire
        # northbound trip or vice versa, making a bound appear not uniform
        northbound_indices = are_northbound.iloc[1:-1][
          are_northbound.iloc[1:-1] == True].index
        # print('northbound_indices:\n{}'.format(northbound_indices))
        southbound_indices = are_southbound.iloc[1:-1][
          are_southbound.iloc[1:-1] == True].index
        # print('southbound_indices:\n{}'.format(southbound_indices))
        # assume argwhere will preserve the index ordering
        if northbound_indices.shape[0] > 2 and southbound_indices.shape[0] > 2:
          route_id = round_trip_stop_times.iloc[0]['route_id']
          route_name = route_stops.iloc[0]['route_name']
          vehicle_id = round_trip_stop_times.iloc[0]['vehicle_id']

          valid_trip_count += 2
          # in this round trip, the northbound trip precedes the southbound trip
          # if northbound_indices[-1] < southbound_indices[0]:
          if np.all(northbound_indices < southbound_indices[0]) \
              and np.all(northbound_indices[-1] < southbound_indices):
            # the southbound trip
            start_time = round_trip_stop_times.iloc[0]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.loc[
              northbound_indices[-1]]['arrived_at']
            # print('end_time: {}'.format(end_time))
            trip_list.append(Trip(
              route_name, route_id, 'N', vehicle_id, start_time, end_time,
              northbound_indices.shape[0]))

            start_time = round_trip_stop_times.loc[
              northbound_indices[-1]]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.iloc[-1]['arrived_at']
            # print('end_time: {}'.format(end_time))

            trip_list.append(Trip(
              route_name, route_id, 'S', vehicle_id, start_time, end_time,
              southbound_indices.shape[0]))
          # elif northbound_indices[0] > southbound_indices[-1]:
          elif np.all(northbound_indices[0] > southbound_indices) \
              and np.all(northbound_indices > southbound_indices[-1]):
            start_time = round_trip_stop_times.iloc[0]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.loc[
              southbound_indices[-1]]['arrived_at']
            # print('end_time: {}'.format(end_time))

            trip_list.append(Trip(
              route_name, route_id, 'S', vehicle_id, start_time, end_time,
              southbound_indices.shape[0]))

            start_time = round_trip_stop_times.loc[
              southbound_indices[-1]]['departed_at']
            # print('start_time: {}'.format(start_time))
            end_time = round_trip_stop_times.iloc[-1]['arrived_at']
            # print('end_time: {}'.format(end_time))

            trip_list.append(Trip(
              route_name, route_id, 'N', vehicle_id, start_time, end_time,
              northbound_indices.shape[0]))
        elif southbound_indices.shape[0] >= 2 \
            and northbound_indices.shape[0] == 0:
          valid_trip_count += 1
          route_id = round_trip_stop_times.iloc[0]['route_id']
          route_name = route_stops.iloc[0]['route_name']
          vehicle_id = round_trip_stop_times.iloc[0]['vehicle_id']

          start_time = round_trip_stop_times.iloc[0]['departed_at']
          # print('start_time: {}'.format(start_time))
          end_time = round_trip_stop_times.iloc[-1]['arrived_at']
          # print('end_time: {}'.format(end_time))

          trip_list.append(Trip(
            route_name, route_id, 'S', vehicle_id, start_time, end_time,
            southbound_indices.shape[0]))
        elif southbound_indices.shape[0] == 0 \
            and northbound_indices.shape[0] >= 2:
          valid_trip_count += 1
          route_id = round_trip_stop_times.iloc[0]['route_id']
          route_name = route_stops.iloc[0]['route_name']
          vehicle_id = round_trip_stop_times.iloc[0]['vehicle_id']

          start_time = round_trip_stop_times.iloc[0]['departed_at']
          # print('start_time: {}'.format(start_time))
          end_time = round_trip_stop_times.iloc[-1]['arrived_at']
          # print('end_time: {}'.format(end_time))

          trip_list.append(Trip(
            route_name, route_id, 'N', vehicle_id, start_time, end_time,
            northbound_indices.shape[0]))
        else:
          pseudo_invalid_trip_count += 1
      else:
        invalid_trip_count += 1
  return trip_list


def assign_warnings_to_trips(
  route_stop_df, stop_time_df, vehicle_assignment_df, warning_df):
  """
  Given four pandas data frames representing warning events, route stops,
  stop events and driver schedules, construct a list of individual route trips,
  assign warning events that occurred during each trip to that trip, then return
  the complete list.
  """
  global trips_with_no_warnings

  global_trip_list = []
  # print('vehicle_assignment_df:\n{}'.format(vehicle_assignment_df.describe()))
  # stop_time_df.sort_values(['arrived_at', 'departed_at'], inplace=True)
  # stop_time_df.set_index(pd.RangeIndex(stop_time_df.shape[0]), inplace=True)

  relevant_route_ids = stop_time_df['route_id'].unique()
  print('route ids among stop times: {}'.format(relevant_route_ids))
  # since DASH A routes are not in teh DB yet...
  available_route_ids = route_stop_df['route_id'].unique()
  print('route ids among route stops: {}'.format(available_route_ids))

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
            # driver during a given trip (of multiple trips) will not switch to
            # a different route and then switch back.

            # although it is possible for some stops to be included that follow
            # the driver's trip start time but precede the route's initial stop,
            # warnings during that interval will be ignored and only those
            # occurring after the first stop departure will be included
            driver_stop_times = stop_time_df.query(
              'route_id == @route_id & '
              'vehicle_id == @vehicle_id & '
              'departed_at >= @driver_start_time & '
              'arrived_at < @driver_end_time')

            driver_stop_times = driver_stop_times.sort_values(
              ['arrived_at', 'departed_at'])

            driver_stop_times.set_index(
              pd.RangeIndex(driver_stop_times.shape[0]), inplace=True)

            # print('route: {}, vehicle: {}, driver: {}, start_time: {}, '
            #       'end_time: {}'.format(route_id, vehicle_id, driver_id,
            #                             driver_start_time, driver_end_time))

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

            route_trip_list = construct_trip_list(route_stops, driver_stop_times)
            # print('found {} route trips'.format(len(route_trip_list)))

            # assume that warning and stop_time records have seconds in their
            # timestamp
            for j in range(len(route_trip_list)):
              trip = route_trip_list[j]
              trip.driver_id = driver_id
              trip.bus_number = driver_assignments.iloc[i].bus_number
              # print('trip_start_time: {}, trip_end_time: {}'.format(trip_start_time, trip_end_time))

              trip_warnings = warning_df.query(
                'bus_number == @trip.bus_number & '
                'loc_time >= @trip.start_time & '
                'loc_time < @trip.end_time')

              if trip_warnings.shape[0] == 0:
                # print('Trip {} for run {}: {} has no warnings'.format(
                #   j, i, [vehicle_id, driver_id, route_id, trip.start_time,
                #       trip.end_time, trip.heading, trip.stop_count]))

                trips_with_no_warnings += 1
              # else:
              #   print('Trip {} for {} has warnings'.format(
              #     i, [vehicle_id, driver_id, route_id, trip.start_time, trip.end_time, trip.heading]))

              warning_assignments = trip_warnings[
                ['vehicle_id', 'driver_id', 'route_id']]

              # print('pre-assignment: {}'.format(warning_df.loc[trip_warnings.index]))
              # warning_df['vehicle_id'].loc[trip_warnings.index] = np.tile(
              #   vehicle_id, trip_warnings.shape[0])
              # warning_df['driver_id'].loc[trip_warnings.index] = np.tile(
              #   driver_id, trip_warnings.shape[0])
              # warning_df['route_id'].loc[trip_warnings.index] = np.tile(
              #   route_id, trip_warnings.shape[0])
              # print('post-assignment: {}'.format(warning_df.loc[trip_warnings.index]))

              # print('pre-assignment: {}'.format(trip_warnings.head(1)))
              trip_warnings.loc[:, 'vehicle_id'] = np.tile(
                vehicle_id, trip_warnings.shape[0])
              trip_warnings.loc[:, 'driver_id'] = np.tile(
                driver_id, trip_warnings.shape[0])
              trip_warnings.loc[:, 'route_id'] = np.tile(
                route_id, trip_warnings.shape[0])
              # print('post-assignment: {}'.format(trip_warnings.head(1)))

              # if not np.all(warning_assignments.values == 0):
              #   print('Assigning some warnings to trip\n{}: {}\nthat have '
              #         'already been assigned to\n{}'.format(i, [
              #     vehicle_id, driver_id, route_id, trip.start_time,
              #     trip.end_time, trip.heading], warning_assignments))

              trip.warnings = trip_warnings
              # what if we use only arrive_at to define both the start and end
              # of a trip, and then split warnings using > and <= at trip joints

              # print('trip warnings: {}'.format(trip.warnings))

            global_trip_list.extend(route_trip_list)
    else:
      print('missing definition for route with id {}'.format(route_id))

  print('valid_trip_count: {}'.format(valid_trip_count))
  print('invalid_trip_count: {}'.format(invalid_trip_count))
  print('pseudo_invalid_trip_count: {}'.format(pseudo_invalid_trip_count))
  print('trips_with_no_warnings: {}'.format(trips_with_no_warnings))
  # TODO: handle unassigned warnings
  return global_trip_list


def construct_longitudinal_data_product(trip_list):
  """Given a list of Trip objects with warnings assigned, create longitudinal
  records and return them as a numpy array """
  output_data = np.ndarray((len(trip_list),), dtype=longitudinal_type)

  # trip being aggregated
  for i in range(len(trip_list)):
    trip = trip_list[i]

    trip_data = np.array([[
      trip.route_name, trip.route_id, trip.heading, trip.driver_id, trip.vehicle_id,
      trip.bus_number, trip.start_time, trip.end_time]])

    unique_warnings, counts = np.unique(
      trip.warnings.loc[:, 'warning_name'].values, return_counts=True)

    warning_data = np.zeros((1, warnings_header.shape[0]))

    for j in range(unique_warnings.shape[0]):
      index = np.nonzero(warnings_header == unique_warnings[j])

      if len(index) > 0:
        assert len(index) == 1
        warning_data[0, index] = counts[j]

    trip_data = np.squeeze(np.concatenate((trip_data, warning_data), axis=1))

    output_data[i] = tuple(trip_data)

  output_data = pd.DataFrame(output_data)

  # print('output_data: {}'.format(output_data.describe()))

  return output_data


def construct_hotspot_data_product(trip_list):
  output_data = np.ndarray(
    (sum([trip.warnings.shape[0] for trip in trip_list]),), dtype=hotspot_type)

  index = 0

  for trip in trip_list:
    if trip.warnings.shape[0] > 0:
      warning_data = trip.warnings.loc[:, ['loc_time', 'warning_name',
                                          'latitude', 'longitude']].values

      trip_data = np.tile([
        trip.route_name, trip.route_id, trip.heading, trip.driver_id,
        trip.vehicle_id, trip.bus_number], (warning_data.shape[0], 1))

      output_data[index:index + warning_data.shape[0]] = np.apply_along_axis(
        to_tuple, 1, np.concatenate((trip_data, warning_data), axis=1))

      index += warning_data.shape[0]

  output_data = pd.DataFrame(output_data)

  # print('output_data: {}'.format(output_data.describe()))

  return output_data


#also identify duplicates when a record is dropped for the second time
def identify_unassigned_warnings(trip_list, warning_df):
  """use the indices of warning data frames assigned to trips to identify
  warnings in warning_df that are not assigned to any trip, """
  w = warning_df.copy()
  print('initial w len: {}'.format(w.shape[0]))

  for trip in trip_list:
    try:
      w = w.drop(trip.warnings.index)
    except ValueError as ve:
      print('1. {}'.format(ve))
      try:
        w = w.drop(list(set(
          warning_df.index.values).intersection(trip.warnings.index.values)))
      except Exception as e:
        print('2. {}'.format(e))
      # pass

  print('initial w len: {}'.format(w.shape[0]))

  for i in range(0, w.shape[0], 10000):
    print(w.iloc[i])

  print('final w len: {}'.format(w.shape[0]))

  return w


if __name__ == '__main__':
  parser = argparse.ArgumentParser()

  parser.add_argument('--db_path', default='ituran_synchromatics_data.sqlite')
  parser.add_argument('--route_stop_table_name', default='route_stop')
  parser.add_argument('--stop_event_table_name', default='stop_time')
  parser.add_argument('--driver_schedule_table_name',
                      default='vehicle_assignment')
  parser.add_argument('--warning_table_name', default='warning')
  parser.add_argument('--hotspot_record_table_name',
                      default='hotspot_data_product')
  parser.add_argument('--longitudinal_record_table_name',
                      default='longitudinal_data_product')
  parser.add_argument('--if_exists', default='append')

  args = parser.parse_args()

  db_path = 'sqlite:///' + args.db_path

  db = create_engine(db_path)

  route_stop_df = pd.read_sql_table(args.route_stop_table_name, db)
  # print('route_stop_df:\n{}'.format(route_stop_df.describe()))

  # Allow for a subset of data to be processed based on a date range
  # start_datetime_str = '02/01/2018 00:00:00'
  # start_datetime = datetime.strptime(
  #   start_datetime_str, '%m/%d/%Y %H:%M:%S').strftime('%m-%d-%Y %H:%M:%S')
  start_datetime = None#'2018-02-01 00:00:00'
  # end_datetime_str = '02/28/2018 23:59:59'
  # end_datetime = datetime.strptime(
  #   end_datetime_str, '%m/%d/%Y %H:%M:%S').strftime('%m-%d-%Y %H:%M:%S')
  end_datetime = None#'2018-02-28 23:59:59'

  if start_datetime is not None and end_datetime is not None:
    stop_time_df = pd.read_sql(
      'select * from {} where arrived_at >= datetime(\'{}\') and arrived_at <= '
      'datetime(\'{}\')'.format(args.stop_event_table_name, start_datetime,
                      end_datetime), con=db)
  else:
    stop_time_df = pd.read_sql_table(args.stop_event_table_name, db)
  print('stop_time_df:\n{}'.format(stop_time_df.describe()))

  if start_datetime is not None and end_datetime is not None:
    vehicle_assignment_df = pd.read_sql(
      'select * from {} where arrived_at >= datetime(\'%s\',\'{}\') and arrived_at <= '
      'datetime(\'%s\',\'{}\')'.format(args.stop_event_table_name, start_datetime,
                      end_datetime), con=db)
  else:
    vehicle_assignment_df = pd.read_sql_table(
      args.driver_schedule_table_name, db)
  print('vehicle_assignment_df:\n{}'.format(vehicle_assignment_df.describe()))

  if start_datetime is not None and end_datetime is not None:
    warning_df = pd.read_sql(
      'select * from {} where arrived_at >= \'{}\' and arrived_at <= '
      '\'{}\''.format(args.stop_event_table_name, start_datetime,
                      end_datetime), con=db)
  else:
    warning_df = pd.read_sql_table(args.warning_table_name, db)
  print('warning_df:\n{}'.format(warning_df.describe()))

  # extend warning df to include columns that uniquely identify trips so that
  # warnings assigned to multiple runs can be discovered.
  warning_ext = pd.DataFrame(
    data=np.zeros((warning_df.shape[0], 3), dtype=np.uint32),
    columns=['vehicle_id', 'driver_id', 'route_id'], index=warning_df.index)

  warning_df = pd.concat([warning_df, warning_ext], axis=1)

  print('warning_df head:\n{}'.format(warning_df.head(2)))

  trip_list = assign_warnings_to_trips(
    route_stop_df, stop_time_df, vehicle_assignment_df, warning_df)
  print('found {} total trips'.format(len(trip_list)))

  # unassigned_warning_data = identify_unassigned_warnings(trip_list, warning_df)
  # unassigned_warning_data.to_sql(
  #   'unassigned_warning', db, if_exists=args.if_exists, chunksize=1000000,
  #   index=False)
  # print(unassigned_warning_data.describe())

  longitudinal_data = construct_longitudinal_data_product(trip_list)
  longitudinal_data.to_sql(
    args.longitudinal_record_table_name, db, if_exists=args.if_exists,
    chunksize=1000000, index=False)
  print(longitudinal_data.describe())

  hotspot_data = construct_hotspot_data_product(trip_list)
  hotspot_data.to_sql(
    args.hotspot_record_table_name, db, if_exists=args.if_exists,
    chunksize=1000000, index=False)
  print(hotspot_data.describe())

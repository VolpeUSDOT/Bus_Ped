# Pedestrian conflict hot spot analysis
# Based on Mobileye Shield+ telematics data from June 2018 data, as stored in the ituran_hotsppot_data.sqlite database
# Starting from 
# https://github.com/dflynn-volpe/Bus_Ped/blob/master/Route_12_kde2.R
# 1. Kernal density using spatstat or ks package
# 2. Clustering with hclust and cluster package ( not implemented yet )

# This follows Event_point_to_line.R, which outputs several processed data files into a directory named for the version of the database. For example, Temp_Event_Dist_Neared_byHour_DASH.RData, which currently has the June 2018 events which could be assigned to a route, and then uses a proximity method to assign the closest route. About 12% of the data appear to be mis-assigned.

# Based on Mobileye Shield+ telematics data from June 2018 data, as stored in the ituran_hotsppot_data.sqlite # Making a test of braking event only hotspots. 
# TODO: Create a function for calculation of kernel density estimates, apply the function in the foreach loop

# Setup ----

library(maps)
library(sp)
library(rgdal)
library(rgeos)
library(ggmap)
library(raster)
library(MASS) 
library(tidyverse) # specify dplyr::select() because of namespace conflicts with raster and MASS
library(cluster)
library(DBI)
library(RSQLite)
library(foreach)
library(doParallel)

# Set working directory and read in data. Set key parameters here:

# <><><><><><><><><><><><><><><><><><><><>
codeloc = "~/git/Bus_Ped/"
rootdir <- "//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data/"
Database = "ituran_synchromatics_data.sqlite" # select version of database to use
bandwithdth_adj = 0.5 # proportion to adjust the bandwidth of the kernel density estimates. at 1, uses the default from bandwidth.nrd
# Set warning type or types to analyze. Braking events in June: 469 aggressive, 34 dangerous 
warning_keywords = c('All', 'Braking', 'PCW', 'PDZ') # One word. E.g. Braking, PCW, PDZ, ME
# Set month to operate over
use_month = '2018-06' # not yet implemented, use this to pick out month of interest. Only June 2018 currently available
# <><><><><><><><><><><><><><><><><><><><>

setwd(rootdir)
version = paste(gsub("\\.sqlite", "", Database), 'version', sep = '_')

load(file.path(version, "Temp_Event_Dist_Nearest_byHour_DASH.RData")) # loads data.frame db_2, which includes the  nearest.route variable from the proximity analysis.

# Load shapefiles and projection
if(length(grep('LADOT_routes.RData', dir('Routes'))) == 0) {
  source(file.path(codeloc, "Route_prep.R")) 
} else { 
  if(!exists("dt_dash")) load(file.path('Routes', "LADOT_routes.RData"))
}

# Before looping over each warning, set up values of whole grid area to analyze. Make this the same for every layer.
d_all <- SpatialPointsDataFrame(coords = db_2[c("longitude","latitude")], data = db_2, proj4string = CRS(proj))

# current area in square kilometers. Extend the range by 10% to cover a wider range
use_lon_range = extendrange(d_all@coords[,1], f = 0.1)
use_lat_range = extendrange(d_all@coords[,2], f = 0.1)

total_area_sqkm = diff(use_lon_range)/1000 * diff(use_lat_range)/1000

# Make each grid cell 50 sq m. So each side needs to be sqrt(50) 
# longitudinal count of grids to use:
lon_n_use = ceiling(diff(use_lon_range) / sqrt(50) )

# latitudeinal count of grids to use:
lat_n_use = ceiling(diff(use_lat_range) / sqrt(50) )

for(warningtype in warning_keywords){ # Start loop over warning types. warningtype = 'PCW'
  
  usewarning = unique(d_all$warning_name)[grep(warningtype, unique(d_all$warning_name))]
  
  if(warningtype == 'All') { usewarning = unique(d_all$warning_name)}
  if(warningtype == 'PCW') { usewarning = c(usewarning, 'ME - Pedestrian Collision Warning')}
  if(warningtype == 'PDZ') { usewarning = c(usewarning, 'ME - Pedestrian In Range Warning')}
  
  # Make route_id name with heading and filter out mismatches for now. Drop a bunch of unneeded columns.
  # Now also applying the warning type filter
  d = d_all@data %>%
    mutate(route_id = make.names(paste(route_name, heading)),
           prox_assigned = paste("DASH", nearest.route),
           mismatch = prox_assigned != route_name) %>%
    filter(!mismatch) %>%
    dplyr::select(-prox_assigned, -loc_time, -LocationTime, -dayhr, -mismatch,
           -nearest.route, -maj.nearest.route, -confidence) %>%
    filter(warning_name %in% usewarning)
  
  # Make it a spatial data frame, only picking out relevant columns
  d <- SpatialPointsDataFrame(coords = d[c("longitude","latitude")], data = d %>% dplyr::select(-longitude, -latitude),
                              proj4string = CRS(proj))
  
  # Work in parallel
  cl = makeCluster(parallel::detectCores())
  registerDoParallel(cl)
  
  # Kernel density estimation from MASS ----
  # We want to translate from density per degree to count per square mile or other more easily interpretable units. So we need to work on projected data, not in units of decimal degrees. Good explanation here: https://www.esri.com/arcgis-blog/products/product/analytics/how-should-i-interpret-the-output-of-density-tools/
  
  foreach(idx = unique(d$route_id), .packages = c("dplyr", "ggmap", 'MASS', 'raster', 'sp', 'reshape')) %dopar% { 
    # idx = unique(d$route_id)[1]
    usedat = d@coords[ d@data$route_id == idx, ]
    
    dens = kde2d(usedat[,1], usedat[,2],
                 h = c(bandwidth.nrd(usedat[,1])*bandwithdth_adj,
                       bandwidth.nrd(usedat[,2])*bandwithdth_adj),
                 n = c(lon_n_use, lat_n_use),
                 lims = c(use_lon_range, use_lat_range))  
   
   # Values in each cell now represent count of warnings across the whole area, total_area_sqkm (15.79 sq km in this example). Let's turn this in to values per square mile.
    # Each grid cell is 50 sq m. So first divide by total area to get count per one square kilometer. Could then multiply by 0.386102 to get counts per square mile, or multiply by 1e6 (1 million) to get events per square meter
    
    dens$z = ( dens$z / total_area_sqkm ) * 1e6  
  
    # Set bottom 75th of the percentile to NA
    dens$z[dens$z <= quantile(dens$z, 0.75)] = NA
    
    # Make density raster into a spatial object
    dimnames(dens$z) = list(dens$x, dens$y)
  
    d_r <- rasterFromXYZ(reshape::melt(dens$z),
                         crs = proj)
  
    # http://openstreetmapdata.com/info/projections
    d_r_ll <- projectRaster(from = d_r,
                            crs = CRS(projargs = "+init=epsg:3857")) # Tranform to mercator lat long
    
    # Write out to spatial data layer for ArcMap work
    writeRaster(d_r_ll, filename = file.path('Raster', paste0("Raster_Unnormalized_", warningtype, '_', idx, ".tif")),
                format = 'GTiff',
                overwrite = TRUE)
    # in ArcMap: open GeoTIFF, change symbology as appropriate.
    
  } # end loop over routes

  # Get number of trips ---
  # Query hotspot table in database
  conn = dbConnect(RSQLite::SQLite(), file.path("Data Integration", Database))
  db = dbGetQuery(conn, "SELECT * FROM longitudinal_data_product")
  
  # filter out trips which have bad matches between Synchromatics and telematics data, by looking at what is in the individual warning data d, which already has the mismatches filtered out.
  
  # Format date/time. %OS for seconds with decimal
  db <- db %>%
    mutate(
      start_time = as.POSIXct(start_time, '%Y-%m-%d %H:%M:%OS', tz = "America/Los_Angeles"),
      end_time = as.POSIXct(end_time, '%Y-%m-%d %H:%M:%OS', tz = "America/Los_Angeles"),
      date = as.Date(format(start_time, '%Y-%m-%d')),
      start_hour = as.numeric(format(start_time, '%H')),
      end_hour = as.numeric(format(end_time, '%H')),
      unique_ID = paste(route_name, heading, driver_id, vehicle_id, bus_number, date, sep = "_"))
  
  # Make same unique identifier for individual warning data d
  d@data <- d@data %>%
    mutate(
      unique_ID = paste(route_name, heading, driver_id, vehicle_id, bus_number, date, sep = "_"))
  
  # Subset db to only unique_ID which are present in individual warning data d
  db <- db[db$unique_ID %in% d$unique_ID,]
  
  # 700 trips out of 21k are dropped
  # Simple query: how many trips were run for each route_name and heading?
  month_trip_count = db %>%
    group_by(route_name, heading) %>%
    summarize(count = n()) %>%
    mutate(rte_head = make.names(paste(route_name, heading)))
  
  # Now re-do the heat map, dividing by month_trip_count for each route name and heading combination
    foreach(idx = unique(d$route_id), .packages = c("dplyr", "ggmap", 'MASS', 'raster', 'sp', 'reshape')) %dopar% { 
    # idx = unique(d$route_id)[1]
    cat(idx, '\n')
    
    usedat = d@coords[ d@data$route_id == idx, ]
    
    dens = kde2d(usedat[,1], usedat[,2],
                 h = c(bandwidth.nrd(usedat[,1])*bandwithdth_adj,
                       bandwidth.nrd(usedat[,2])*bandwithdth_adj),
                 n = c(lon_n_use, lat_n_use),
                 lims = c(use_lon_range, use_lat_range))  
    
    # Values in each cell now represent count of warnings across the whole area, total_area_sqkm (15.79 sq km for Dash F N, but 28.4 sq km for full study area). Let's turn this in to values per square mile.
    # Each grid cell is 50 sq m. So first divide by total area to get count per one square kilometer. Could then multiply by 0.386102 to get counts per square mile, or multiply by 1e6 (1 million) to get events per square meter
    
    dens$z = ( dens$z / total_area_sqkm ) * 1e6  
    
    # Set bottom 75th of the percentile to NA
    dens$z[dens$z <= quantile(dens$z, 0.75)] = NA
    
    # Now standardize by dividing by the total number of trips. Use the data frame month_trip_count.
    count_i = month_trip_count %>% ungroup() %>% filter(rte_head == idx) %>% dplyr::select(count)
    
    dens$z = dens$z / as.numeric(count_i) * 100 # making it per 100 trips for better units
    
    # Make density raster into a spatial object
    dimnames(dens$z) = list(dens$x, dens$y)
    
    d_r <- rasterFromXYZ(reshape::melt(dens$z),
                         crs = proj)
    
    # http://openstreetmapdata.com/info/projections
    d_r_ll <- projectRaster(from = d_r,
                            crs = CRS(projargs = "+init=epsg:3857")) # Tranform to mercator lat long, to match stamen map base layers
    
    # Write out to spatial data layer for ArcMap work
    writeRaster(d_r_ll, filename = file.path('Raster', paste0("Raster_Normalized_", warningtype, '_',idx, ".tif")),
                format = 'GTiff',
                overwrite = TRUE)
    # in ArcMap: open GeoTIFF, change symbology as appropriate.
  } # end loop over routes
} # end loop over warning types

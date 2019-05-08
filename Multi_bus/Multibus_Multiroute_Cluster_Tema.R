# Calculate clusters with better memory optimizing 


# Setup ----

library(sp)
library(rgdal)
library(rgeos)
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
# Don't try to run All on a laptop! will need a whole lot more RAM or a different distance calculation engine.                    
warning_keywords = c(#'All', 
                      'Braking'
                      ,'PCW' 
                      #  'PDZ'
                      #   'PDZ-LR',
                      #   'PDZ-R',
                      #   'PDZ - Left Front',
                      #   'ME - Pedestrian In Range Warning'
                      # 
                    ) # Should be able to use just one key word, but now trying to split PDZ warnings out individually

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

# Get number of trips ---
# Query hotspot table in database
conn = dbConnect(RSQLite::SQLite(), file.path("Data Integration", Database))


####################################################

month_start_list <- list('2018-01-01', '2018-02-01', '2018-03-01', '2018-04-01', '2018-05-01', '2018-06-01',
                         '2018-07-01', '2018-08-01', '2018-09-01', '2018-10-01', '2018-11-01', '2018-12-01')
month_end_list <- list('2018-01-31', '2018-02-28', '2018-03-31', '2018-04-30', '2018-05-31', '2018-06-30',
                       '2018-07-31', '2018-08-31', '2018-09-30', '2018-10-31', '2018-11-30', '2018-12-31')
month_name_list <- list('Jan', 'Feb', 'March', 'April', 'May', 'June', 'July', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec')


for(j in 4:4){
  print(paste0("this is month: ", month_name_list[j]))

  db = dbGetQuery(conn, paste0("SELECT * FROM longitudinal_data_product WHERE start_time 
                  >= '",month_start_list[j], " 00:00:00' AND start_time
                  <= '",month_end_list[j], " 23:59:59' LIMIT 300"))
  
  print(paste0("checkpoint1, ", j))
  
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
  
  
  print(paste0("checkpoint2, ", j))
  
  # Make same unique identifier for individual warning data d
  d_all@data <- d_all@data %>%
    mutate(
      unique_ID = paste(route_name, heading, driver_id, vehicle_id, bus_number, date, sep = "_"))
  
  # Subset db to only unique_ID which are present in individual warning data d
  db <- db[db$unique_ID %in% d_all$unique_ID,]
  
  # 700 trips out of 21k are dropped
  # Simple query: how many trips were run for each route_name and heading?
  month_trip_count = db %>%
    group_by(route_name, heading) %>%
    summarize(count = n()) %>%
    mutate(rte_head = make.names(paste(route_name, heading)))
  
  for(warningtype in warning_keywords){ # Start loop over warning types. warningtype = 'PCW'
    
    usewarning = unique(d_all$warning_name)[grep(warningtype, unique(d_all$warning_name))]
    
    # Don't try to run All on a laptop! 
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
    
    # Work in parallel, only for All, Braking, or PCW. PDZ too memory intensive
    if(warningtype %in% c('All', 'PCW', 'Braking')){
      cl = makeCluster(parallel::detectCores())
      registerDoParallel(cl)
    } 
    
    # Parameters:
    min.cluster = 50 # minimum number of values in a cluster.
    
    writeLines(c(""), file.path('Cluster', paste0(warningtype, "_log_", month_name_list[j], ".txt"))) #CHANGED FILE NAME FOR MONTH 
    
    # Start parallel over route_id ----
    # PDZ too memory intensive for %dopar% parallel, so changing to %do% for sequential instead
    foreach(idx = unique(d$route_id), .packages = c('dplyr', 'sp', 'rgdal')) %do% { 
      sink(file.path('Cluster', paste0(warningtype, "_log_", month_name_list[j], ".txt")), append=TRUE) #CHANGED FILE NAME FOR MONTH
      
      # idx = unique(d$route_id)[1]
      usedat = d@coords[ d@data$route_id == idx, ]
      
      starttime = Sys.time()
      cat(as.character(starttime), idx, format(nrow(usedat), big.mark = ","), "\n")
      
      d.dist <- spDists(usedat) # spDists gives distance in km, increasing here to m. 75k observations too many for spDists all at once. Need to loop over routes.
      
      d.clust <- hclust(as.dist(d.dist), method = "single") # average: linkage by unweighted pairwise group method with arithmatic mean, UPGMA. Change method to "single" for single linkage, see ?hclust for more options. Single linkage is likely the what Crimestat refers to as nearest neighbor
      
      # The cluster package can identify optimal number of clusters, as an alternative to simply setting a minimum number of values in a cluster. Here the popular Gap statistic is used to identify the optimum number of clusters, created by k-means clustering instead of the single-linkage hierarchical clustering above.
      # This step may take several minutes; set "doGap" to TRUE to run this step.
      doGap = FALSE
      
      if(doGap){
        gap.metric.km <- clusGap(d.proj@coords, FUNcluster = kmeans, 
                                 K.max = 100,
                                 B = 100, verbose = interactive())
        plot(gap.metric.km)
        k <- maxSE(gap.metric.km$Tab[, "gap"], gap.metric.km$Tab[, "SE.sim"], method="Tibs2001SEmax")
        cat("Gap estimate for optimal number of clusters:", k)
      }
      
      d.cut <- cutree(d.clust, k = ifelse(nrow(usedat) < 100, nrow(usedat), 100))
      
      # Cluster names to not show, as these are below the minimum number of members:
      less.than.min = names(table(d.cut))[table(d.cut) <= min.cluster]
      
      dc <- data.frame(d[d$route_id == idx,], d.cut, lat = coordinates(d[d$route_id == idx,])[,2], lon = coordinates(d[d$route_id == idx,])[,1])
    
    # Aggregated by group and summarize. Can add StatusName to group_by
    # Omit clusters which are fewer than the minimum number of members to show using filter() statement
    dc2 <- dc %>%
      group_by(d.cut) %>%
      summarize(lat.m = mean(lat),
                lon.m = mean(lon),
                lat.sd = sd(lat),
                lon.sd = sd(lon),
                n = n()
      ) %>%
      filter(!d.cut %in% less.than.min)
    
    
    # Convex Hulls ----
    # Calculate hulls for each distinct set of points deterimined by the d.cut of the clustering.
    # Loop over sets of points and apply the chull() function, then use this to create SpatialPolygons based on those values.
    # Check to see if we have at least one cluster
    if(nrow(dc2) > 0) {
       hulllist = list()
      for(i in dc2$d.cut){ # i = 1
        cv <- chull(dc[c("lon","lat")][d.cut == i,])
        hulllist[[as.character(i)]] = Polygons(list(Polygon(dc[c("lon","lat")][d.cut == i,][cv,])), i)
      }
      
      ConvHullPoly <- SpatialPolygons(hulllist, proj4string = CRS(proj))
      
      stopifnot(identical(as.character(names(ConvHullPoly)), as.character(dc2$d.cut)))
      
      n_points = dc2$n
        
      # Normalize by number of trips ----
      # Now standardize by dividing by the total number of trips. Use the data frame month_trip_count.
      count_i = month_trip_count %>% ungroup() %>% filter(rte_head == idx) %>% dplyr::select(count)
      
      n_points_norm = n_points / as.numeric(count_i) * 100 # making it per 100 trips for better units
      
      ConvHullPoly_df = SpatialPolygonsDataFrame(ConvHullPoly, data = data.frame(n_points,
                                                                                 n_points_norm,
                                                                                 row.names = names(ConvHullPoly@polygons)))
      # Put in Mercator lat long and write out 
      conv_ll <- spTransform(ConvHullPoly_df, CRS(projargs = "+init=epsg:3857")) # Tranform to mercator lat long
      
      # Write out to spatial data layer for ArcMap work
      writeOGR(conv_ll, dsn = file.path(rootdir, paste0("Cluster_", month_name_list[j])), layer = paste0("Hot_Spot_", warningtype, '_', idx),
                  driver = 'ESRI Shapefile') #CHANGED FILE NAME FOR MONTH ^^^
      
      endtime <- Sys.time() - starttime
      cat(round(endtime, 2), attr(endtime, "units"), "\n")
      sink()
      } # end check for at least one cluster
    } # end route_id foreach loop
  } # end Warning type loop
}

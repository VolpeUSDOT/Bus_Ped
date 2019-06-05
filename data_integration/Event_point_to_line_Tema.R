# Matching DASH point to lines, and outputting values which do not match
# Working with interim data product of integrated telematics and Synchromatics data

library(tidyverse)
library(rgdal)
library(rgeos) # for gDistance
library(DBI) # to query sqlite database
library(RSQLite)
library(ggmap)

# Load data ----

# <><><><><><><><><><><><><><><><><><><><>
codeloc = "~/git/Bus_Ped/"
rootdir <- "//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data/"
Database = "ituran_synchromatics_data.sqlite" # select version of database to use
# <><><><><><><><><><><><><><><><><><><><>

setwd(rootdir)
version = paste(gsub("\\.sqlite", "", Database), 'version', sep = '_')
system(paste('mkdir -p', version))
system(paste('mkdir -p', file.path(version, 'Figures')))

if(length(grep('LADOT_routes.RData', dir('Routes'))) == 0) {
  source(file.path(codeloc, "Route_prep.R")) 
} else { 
  if(!exists("dt_dash")) load(file.path('Routes', "LADOT_routes.RData")) 
}
# Query hotspot table in database
conn = dbConnect(RSQLite::SQLite(), file.path("Data Integration - All Months", Database))

########################

month_list <- list('2018-01-01 to 2018-01-31', '2018-02-01 to 2018-02-28', '2018-03-01 to 2018-03-31', 
                   '2018-04-01 to 2018-04-30', '2018-05-01 to 2018-05-31', '2018-06-01 to 2018-06-30',
                   '2018-07-01 to 2018-07-31', '2018-08-01 to 2018-08-31', '2018-09-01 to 2018-09-30',
                   '2018-10-01 to 2018-10-31', '2018-11-01 to 2018-11-30', '2018-12-01 to 2018-12-31')
month_start_list <- list('2018-01-01', '2018-02-01', '2018-03-01', '2018-04-01', '2018-05-01', '2018-06-01',
                         '2018-07-01', '2018-08-01', '2018-09-01', '2018-10-01', '2018-11-01', '2018-12-01')
month_end_list <- list('2018-01-31', '2018-02-28', '2018-03-31', '2018-04-30', '2018-05-31', '2018-06-30',
                       '2018-07-31', '2018-08-31', '2018-09-30', '2018-10-31', '2018-11-30', '2018-12-31')
month_name_list <- list('Jan', 'Feb', 'March', 'April', 'May', 'June', 'July', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec')

for(j in 1:length(month_name_list)){
  print("this is j:", j)
  
  
#j = 3
 # Updated using datetime() instead of to_timestamp() for SQLite
  db = dbGetQuery(conn, paste0("SELECT * FROM hotspot_data_product WHERE loc_time 
                  >= '",month_start_list[j], " 00:00:00' AND loc_time
                  <= '",month_end_list[j], " 23:59:59'"))
  
  
  # Prep data frames as spatial
  # Make it a spatial data frame, only picking out relevant columns
  if(class(db) != "SpatialPointsDataFrame"){
    db$LocationTime = as.character(db$loc_time)
    
    db = db %>% filter(!is.na(latitude) & !is.na(longitude))
    db <- SpatialPointsDataFrame(coords = db[c("longitude","latitude")], data = dplyr::rename(db, ll.lat = latitude, ll.lon = longitude),
                                 proj4string = CRS("+proj=longlat +datum=WGS84 +no_defs +ellps=WGS84 +towgs84=0,0,0"))
    
    
    # Format date/time. %OS for seconds with decimal
    db@data <- db@data %>%
      mutate(#date = as.Date(unlist(lapply(strsplit(loc_time, " "), function(x) x[1]))),
        datetime = as.POSIXct(loc_time, '%Y-%m-%d %H:%M:%OS', tz = "America/Los_Angeles"),
        date = as.Date(format(datetime, '%Y-%m-%d')),
        hour = as.numeric(format(datetime, '%H')))
    db.ll = db
    db <- spTransform(db, CRS(proj))
    
  }
  
  
  # write.csv(db@data, file = 'Ituran_Data_Hotspot.csv', row.names=F)
  
  # Event to downtown DASH ---
  # 1. calculate distance between each point and each DASH route using gDistance
  
  system.time( dt_dash_dist_mat <- gDistance(db, dt_dash, byid=T)/1609.34 ) # convert from meters to miles
  
  # 2. Make a vector of which route is the closest, and a vector of the minimum distance value. Now doing both in a dplyr step.
  
  # dt_dash_route <- apply(dt_dash_dist_mat, 2, function(x) which(x == min(x))) # was breaking with larger data set, maybe one point was exactly equidistant between two routes...
  
  print(paste0("checkpoint1, ", j))
  
  
  rownames(dt_dash_dist_mat) = as.character(dt_dash@data$RouteNameS)
  dt_dash_dist_mat = as_tibble(t(dt_dash_dist_mat))
  
  dt_dash_route = dt_dash_dist_mat %>%
    rowwise() %>%
    mutate(mindist = min(A, B, D, E, F),
           mindist_route = which.min(c(A, B, D, E, F))) %>%
    ungroup()
  
  dt_dash_route$mindist_route = as.factor(as.character(dt_dash_route$mindist_route))
  levels(dt_dash_route$mindist_route) = as.character(dt_dash@data$RouteNameS)
  
  db_d <- data.frame(db@coords, db@data, dt_dash_route = dt_dash_route$mindist_route, dt_dash_dist = dt_dash_route$mindist)
  
  db_d$dt_dash_route = factor(db_d$dt_dash_route, levels = as.character(dt_dash@data$RouteNameS))
  
  # save(db_d, file = file.path(version, "Test_Event_Dist.RData"))
  
  rm(dt_dash_dist_mat, dt_dash_route)
  
  # Process to nearest route for each individual event ----
  
  min.dist.use = 0.1 # If nearest route is greater than 0.1 miles away, return NA
  
  
  print(paste0("checkpoint2, ", j))
  
  route_id = vector()
  for(i in 1:nrow(db_d)){
    if(db_d[i,"dt_dash_dist"] > min.dist.use){
      route_id = c(route_id, NA)
    } else {
      route_id = c(route_id, as.character(db_d[i,"dt_dash_route"]))
    }
  }
  
  db_d <- data.frame(db_d, nearest.route = route_id)
  
  save(db_d, file = file.path(version, paste("Event_Dist_Nearest_DASH_", month_name_list[j], ".RData"))) #CHANGED FILE NAME FOR MONTH
  
  # Process within day and hour ----
  # table(db_d$day, db_d$nearest.route)
  # Within each day and hour, apply the majority of route/system to each event.
  # length(unique(dayhr)) = 1781 combinations of day and hour
  db_d$dayhr <- paste(db_d$date, formatC(db_d$hour, width = 2, flag = 0), sep = ".")
  
  maj.nearest.route <- confidence <- vector()
  
  counter = 1
  starttime = Sys.time()
  
  for(i in unique(db_d$dayhr)){ # i = unique(db_d$dayhr)[5]# [sample(1:length(unique(dayhr)), 5)] 
    # i = '2018-06-25.12'
    dx <- db_d[db_d$dayhr == i,]
    
    dxx <- sort(table(dx$nearest.route), decreasing = T)
    dxx <- dxx[dxx != 0]
    
    maj.nearest.route = c(maj.nearest.route, names(dxx[1]))
    confidence = c(confidence, dxx[1]/sum(dxx))
    
    if(counter %% 500 == 0) cat(counter, " . ")
    counter = counter + 1
  }
  timediff = Sys.time() - starttime
  cat(round(timediff, 2), attr(timediff, "units"), "elapsed \n")
  
  maj.res <- data.frame(dayhr = unique(db_d$dayhr), maj.nearest.route, confidence)
  
  db_2 <- left_join(db_d, maj.res, by = "dayhr")
  
  save(db_2, file = file.path(version, paste0("Event_Dist_Nearest_byHour_DASH_", month_name_list[j], ".RData"))) #CHANGED FILE NAME FOR MONTH
  # write.csv(db_2, file = file.path(version, "Temp_Event_Dist_Nearest_byHour_DASH.csv"), row.names = F)
  
  # Process within day and hour block ----
  # table(db_d$day, db_d$nearest.route)
  
  # Within each day and 3-hour time block, apply the majority of route/system to each event.
  # length(unique(db_2$dayhr.block)) = 748 combinations of day and hour
  hrblock <- cut(db_2$hour, breaks = c(0, 3, 6, 9, 12, 15, 18, 21, 24), include.lowest = T)
  
  db_2$dayhr.block <- paste(db_2$day, hrblock, sep = ".")
  
  maj.nearest.route.block <- confidence.block <- vector()
  
  print(paste0("checkpoint3, ", j))
  
  counter = 1
  starttime = Sys.time()
  
  for(i in unique(db_2$dayhr.block)){ # i = unique(db_2$dayhr.block)[1]# [sample(1:length(unique(db_2$dayhr.block)), 5)]
    dx <- db_2[db_2$dayhr.block == i,]
    
    dxx <- sort(table(dx$nearest.route), decreasing = T)
    dxx <- dxx[dxx != 0]
    
    maj.nearest.route.block = c(maj.nearest.route.block, names(dxx[1]))
    confidence.block = c(confidence.block, dxx[1]/sum(dxx))
    
    if(counter %% 500 == 0) cat(counter, " . ")
    counter = counter + 1
  }
  timediff = Sys.time() - starttime
  
  
  
  cat(round(timediff, 2), attr(timediff, "units"), "elapsed \n")
  
  maj.res <- data.frame(dayhr.block = unique(db_2$dayhr.block), maj.nearest.route.block, confidence.block)
  
  db_3 <- left_join(db_2, maj.res, by = "dayhr.block")
  
  
  
  save(db_3, file = file.path(version, paste0("Event_Dist_Nearest_byHourBlock_DASH_", month_name_list[j], ".RData"))) #CHANGED FILE NAME FOR MONTH
  # write.csv(db_3, file = file.path(version, "Temp_Event_Dist_Nearest_byHourBlock_DASH.csv"), row.names = F)
  
  # Find mismatches ----
  # Find events which don't match between integrated data route ID and high-confidence identification by proximity
  # Just use the nearest.route for now.
  
  db_mis <- db_2 %>%
    mutate(prox_assigned = paste("DASH", nearest.route),
           mismatch = prox_assigned != route_name) %>%
    filter(mismatch)
  
  
  table(db_2$nearest.route)
  table(db_2$maj.nearest.route)
  table(db_2$route_name)
  
  table(db_mis$route_name)
  table(db_mis$prox_assigned)
  
  print(paste0("checkpoint4, ", j))
  
  # Plot mismatches ----
  
  ggplot(db_mis) +
    geom_point(aes(longitude, latitude, color = route_name)) +
    facet_wrap(~prox_assigned)
  ggsave(file.path(version, paste0("Figures/Simple_mismatch_plot_", month_name_list[j], ".jpg"))) #CHANGED FILE NAME FOR MONTH
  
  print(paste0("checkpoint5, ", j))
  
  if(length(grep("Basemaps", dir("Routes"))) == 0){
    map_toner_hybrid_13 = get_stamenmap(bb, maptype = "toner-hybrid", zoom = 13)
    
    map_toner_13 = get_stamenmap(bb, maptype = "toner", zoom = 13)
    map_toner_12 = get_stamenmap(bb, maptype = "toner", zoom = 12)
    map_toner_11 = get_stamenmap(bb, maptype = "toner", zoom = 11)
    
    save(list=c("map_toner_hybrid_13", "map_toner_13", "map_toner_12", "map_toner_11"), 
         file = "Basemaps.RData")
  } else { 
    load(file.path('Routes', "Basemaps.RData")) }
  
  print(j)
  
  # Fortify and join for plotting lines
  dt_dash.df <- data.frame(id=rownames(dt_dash.ll@data),
                           values= length(dt_dash.ll),
                           dt_dash.ll@data, stringsAsFactors=F)
  data_fort   <- fortify(dt_dash.ll)
  dt_dash_merged <- plyr::join(data_fort, dt_dash.df, by="id")
  
  # Project db_mis as spatial
  db_ll <- SpatialPointsDataFrame(coords = db_mis[c("longitude","latitude")], data = db_mis,
                                  proj4string = CRS(proj))
  
  db_ll <- spTransform(db_ll, CRS("+proj=longlat +datum=WGS84 +no_defs +ellps=WGS84 +towgs84=0,0,0"))
  
  db_ll@data <- data.frame(db_ll, db_ll@coords)
  
  print(paste0("checkpoint6, ", j))
  
  ggmap(map_toner_13, extent = "device") +
    geom_path(data = dt_dash_merged, mapping = aes(x = long, y = lat, color = RouteNameS), size = 2) +
    geom_point(data = db_ll@data, 
               mapping = aes(x = longitude.2, y = latitude.2, color = route_name), size = 3, alpha = 0.5) +
    #scale_colour_manual(values = c("purple", "firebrick", "midnightblue", "darkgoldenrod1", "magenta","darkorange4", "cyan4", "bisque"),
                        #guide = guide_legend(
                          #override.aes = list(
                            #linetype = c(rep("solid", 3), rep("blank", 3), rep("solid", 2)),
                            #shape = c(rep(NA, 3), rep(16, 3), rep(NA, 2)) ))) +
    
    ggtitle("Plotting mismatches")
  
  print(paste0("checkpoint7, ", j))
  
  ggsave(file.path(version, paste0("Figures/Mapped_all_mismatch_plot_", month_name_list[j], ".jpg"))) #CHANGED FILE NAME FOR MONTH
  
  print(paste0("checkpoint8, ", j))
  
  head(db_mis)
  write.csv(db_mis, file = file.path(version, paste0("Event_Dist_Mismatch_", month_name_list[j], ".csv")), row.names = F) #CHANGED FILE NAME FOR MONTH

  print(paste0("checkpoint9, ", j))
  
write.csv(data.frame('Column' = names(db_mis),
                     'Description' = 
                       c("Longitude - Albers equal area projection",
                         "Latitude - Albers equal area projection",
                         "Synchromatics assigned route name",
                         "Synchromatics route ID",
                         "Heading",
                         "Driver ID",
                         "Vehicle ID",
                         "Bus number",
                         "Location time from telematics",
                         "Warning type from telematics",
                         "Latitude - decimal degree",
                         "Longitude - decimal degree",
                         "Location time copy",
                         "Location time formatted in R",
                         "Date",
                         "Hour of day",
                         "Name of nearest Downtown DASH route",
                         "Distance in miles from point to nearest route",
                         "Nearest route formatted in R",
                         "Day-hour block for this warning",
                         "Beta: majority-vote nearest route by day-hour block",
                         "Beta: confidence expressed in percent of events in this day-hour block in this majority-vote route",
                         "Beta: day-hour group of 3 hour time blocks",
                         "Name of nearest Downtown DASH route formatted to match sychormatics",
                         "Mismatch between Synchromatics and proximity method")
), file = file.path(version, paste0("Temp_Event_Dist_Mismatch_info_", month_name_list[j], ".csv")), row.names = F)
}
################################

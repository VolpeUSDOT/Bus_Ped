# Matching DASH point to lines, and outputting values which do not match
# Working with interim data product of integrated telematics and Synchromatics data

library(tidyverse)
library(rgdal)
library(rgeos) # for gDistance
library(DBI) # to query sqlite database
library(RSQLite)


# Event to downtown DASH
dt_dash_dist_mat <- gDistance(db, dt_dash, byid=T)/1609.34 # convert to miles
rownames(dt_dash_dist_mat) = dt_dash@data$RouteNameS[match(rownames(dt_dash_dist_mat), rownames(dt_dash@data))]
dt_dash_route <- unlist(lapply(apply(dt_dash_dist_mat, 2, function(x) which(x == min(x))), function(x) names(x[1]))) 
dt_dash_dist <- apply(dt_dash_dist_mat, 2, min)

db_d <- data.frame(db@coords, db@data, dt_dash_route, dt_dash_dist, co_dash_route, co_dash_dist, metro_route, metro_dist)


save(db_d, file = "Event_Dist.RData")
write.csv(db_d, file = "Event_Dist.csv", row.names = F)

rm(metro_dist_mat, co_dash_dist_mat, dt_dash_dist_mat,
   metro_dist, co_dash_dist, dt_dash_dist)



# Process to nearest route for each individual event

min.dist.route.num <- apply(db_d[,c("dt_dash_dist","co_dash_dist")], MARGIN = 1, which.min)

min.dist.route.id <- db_d[,c("dt_dash_route","co_dash_route")] 
for(i in 1:ncol(min.dist.route.id)){ min.dist.route.id[,i] = as.character(min.dist.route.id[,i]) }

min.dist.use = 0.1 # If nearest route is greater than 0.1 miles away, return NA

route_id = vector()
for(i in 1:nrow(min.dist.route.id)){
  if(db_d[i,c("dt_dash_dist","co_dash_dist")][min.dist.route.num[i]] > min.dist.use){
    route_id = c(route_id, NA)
  } else {
    route_id = c(route_id, min.dist.route.id[i, min.dist.route.num[i]])
  }
}

bus.system = c("Downtown DASH", "Community DASH")[min.dist.route.num]

bus.system[is.na(route_id)] = NA

db_d <- data.frame(db_d, nearest.route = route_id, bus.system)

save(db_d, file = "Event_Dist_Nearest_DASH.RData")
write.csv(db_d, file = "Event_Dist_Nearest_DASH.csv", row.names = F)


# Process within day and hour
# table(db_d$day, db_d$nearest.route)
# Within each day and hour, apply the majority of route/system to each event.
# length(unique(dayhr)) = 1781 combinations of day and hour
db_d$hour <- format(strptime(db_d$LocationTime, "%Y-%m-%d %H:%M:%S"), "%H")
db_d$dayhr <- paste(db_d$day, db_d$hour, sep = ".")

maj.nearest.route <- maj.bus.system <- confidence <- vector()

counter = 1
starttime = Sys.time()

for(i in unique(db_d$dayhr)){ # i = unique(db_d$dayhr)[5]# [sample(1:length(unique(dayhr)), 5)] 
  # i = "31.17"  for example of where nearest route is NA for some, but can find others close
  # i = "31.15" or i = "42.17" for where no nearest route is within 0.1 mi
  dx <- db_d[db_d$dayhr == i,]
  
  dxx <- sort(table(dx$nearest.route), decreasing = T)
  dxx <- dxx[dxx != 0]
  
  dx2 <- sort(table(dx$bus.system), decreasing = T)
  dx2 <- dx2[dx2 != 0]
  
  maj.nearest.route = c(maj.nearest.route, names(dxx[1]))
  maj.bus.system = c(maj.bus.system, names(dx2[1]))
  confidence = c(confidence, dxx[1]/sum(dxx))
  
  # TO DO: reprocess to get the distance to the majority-rule nearest route, for each even t
  # if(maj.bus.system == "Community DASH"){
  #   maj.dist <- dx$co_dash_dist
  # } 
  
  if(counter %% 500 == 0) cat(counter, " . ")
  counter = counter + 1
}
timediff = Sys.time() - starttime
cat(round(timediff, 2), attr(timediff, "units"), "elapsed \n")

maj.res <- data.frame(dayhr = unique(db_d$dayhr), maj.nearest.route, maj.bus.system, confidence)

db_2 <- left_join(db_d, maj.res, by = "dayhr")

save(db_2, file = "Event_Dist_Nearest_byHour_DASH.RData")
write.csv(db_2, file = "Event_Dist_Nearest_byHour_DASH.csv", row.names = F)


#### 


# Process within day and hour block
# table(db_d$day, db_d$nearest.route)

# Within each day and 3-hour time block, apply the majority of route/system to each event.
# length(unique(db_2$dayhr.block)) = 748 combinations of day and hour
hrblock <- cut(db_2$hour, breaks = c(0, 3, 6, 9, 12, 15, 18, 21, 24), include.lowest = T)

db_2$dayhr.block <- paste(db_2$day, hrblock, sep = ".")

maj.nearest.route.block <- maj.bus.system.block <- confidence.block <- vector()

counter = 1
starttime = Sys.time()

for(i in unique(db_2$dayhr.block)){ # i = unique(db_2$dayhr.block)[1]# [sample(1:length(unique(db_2$dayhr.block)), 5)]
  dx <- db_2[db_2$dayhr.block == i,]
  
  dxx <- sort(table(dx$nearest.route), decreasing = T)
  dxx <- dxx[dxx != 0]
  
  dx2 <- sort(table(dx$bus.system), decreasing = T)
  dx2 <- dx2[dx2 != 0]
  
  maj.nearest.route.block = c(maj.nearest.route.block, names(dxx[1]))
  maj.bus.system.block = c(maj.bus.system.block, names(dx2[1]))
  confidence.block = c(confidence.block, dxx[1]/sum(dxx))
  
  if(counter %% 500 == 0) cat(counter, " . ")
  counter = counter + 1
}
timediff = Sys.time() - starttime
cat(round(timediff, 2), attr(timediff, "units"), "elapsed \n")

maj.res <- data.frame(dayhr.block = unique(db_2$dayhr.block), maj.nearest.route.block, maj.bus.system.block, confidence.block)

db_3 <- left_join(db_2, maj.res, by = "dayhr.block")

save(db_3, file = "Event_Dist_Nearest_byHourBlock_DASH.RData")
write.csv(db_3, file = "Event_Dist_Nearest_byHourBlock_DASH.csv", row.names = F)


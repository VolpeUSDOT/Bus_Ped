# Based on Mobileye Shield+ telematics data from June 2018 data, as stored in the ituran_hotsppot_data.sqlite # Making a test of braking event only hotspots. 
# TODO: separate out the calculation of hotspot kernel density estimates from the visualization steps.
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

# Set working directory and read in data
# <><><><><><><><><><><><><><><><><><><><>
codeloc = "~/git/Bus_Ped/"
rootdir <- "//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data/"
Database = "ituran_synchromatics_data.sqlite" # select version of database to use
# <><><><><><><><><><><><><><><><><><><><>

setwd(rootdir)
version = paste(gsub("\\.sqlite", "", Database), 'version', sep = '_')

load(file.path(version, "Temp_Event_Dist_Nearest_byHour_DASH.RData"))

# Load shapefiles
if(length(grep('LADOT_routes.RData', dir('Routes'))) == 0) {
  source(file.path(codeloc, "Route_prep.R")) 
} else { 
  if(!exists("dt_dash")) load(file.path('Routes', "LADOT_routes.RData"))
}

d <- db_2

# <><><><><><><><><><><><>
# Set warning type or types to analyze. Braking events in June: 469 aggressive, 34 dangerous 
warning_keyword = 'Braking' # One word
usewarning = unique(d$warning_name)[grep(warning_keyword, unique(d$warning_name))]
# <><><><><><><><><><><><>


# Make route_id name with heading and filter out mismatches for now. Drop a bunch of unneeded columns.
# Now also applying the warning type filter
d = d %>%
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

# Get data frame for plotting 
dc <- data.frame(d@data, lat = coordinates(d)[,2], lon = coordinates(d)[,1])

# Make a lat long projection 
d_ll_proj = spTransform(d, CRS("+proj=longlat +datum=WGS84"))

# Kernal density in ggmap ----

par.reset = par(no.readonly = T)

if(length(grep("Basemaps", dir("Routes"))) == 0){
  
  bb = bbox(d_ll_proj)
  bb = matrix(c(expand_range(bb[1,], mul = 0.1),
            expand_range(bb[2,], mul = 0.05)), nrow = 2, byrow = T)
  bb = as.vector(bb)
  
  map_toner_hybrid_13 = get_stamenmap(bb, maptype = "toner-hybrid", zoom = 13)
  
  map_toner_hybrid_14 = get_stamenmap(bb, maptype = "toner-hybrid", zoom = 14)
  
  map_toner_13 = get_stamenmap(bb, maptype = "toner", zoom = 13)
  
  map_toner_14 = get_stamenmap(bb, maptype = "toner", zoom = 14)

  save(list=c("map_toner_hybrid_13", "map_toner_13", "map_toner_hybrid_14", "map_toner_14"), 
       file = file.path('Routes', "Basemaps.RData"))
} else { 
  load(file.path('Routes', "Basemaps.RData")) 
  }

# write.csv(d_ll_proj@data, file = file.path(version, 'Event_Dist_Processed.csv'), row.names=F)

# writeOGR(d_ll_proj, dsn = version, layer = 'Event_Dist_Processed', driver = 'ESRI Shapefile')

# Work in parallel
cl = makeCluster(parallel::detectCores())
registerDoParallel(cl)

# Loop over route ID and heading
pdf(file.path(version, 'Figures', paste0('Hotspots_by_Heading_', warning_keyword, '.pdf')), width = 10, height = 10)
foreach(idx = unique(d_ll_proj$route_id), .packages = c("dplyr", "ggmap")) %dopar% { 
  # idx=unique(d_ll_proj$route_id)[1]
    
  cat(idx, "\n")
  map1 <- ggmap(map_toner_14, extent = 'device') + 
    stat_density2d(data = d_ll_proj@data %>% filter(route_id == idx), aes(x = ll.lon, y = ll.lat,
                                  fill = ..level.., alpha = ..level..),
                   size = 0.01, bins = 8, geom = 'polygon')
  
  print(map1 + ggtitle(paste("Warning density", idx))  +
          scale_fill_gradient(low = "blue", high = "red", 
                              guide_legend(title = "Warning density")) +
          scale_alpha(range = c(0.1, 0.8), guide = FALSE) )

}

dev.off()

# Manual approach with kernel density estimation from MASS ----

# We want to translate from density per degree to count per square mile or other more easily interpretable units. So we need to work on projected data, not in units of decimal degrees. Good explanation here: https://www.esri.com/arcgis-blog/products/product/analytics/how-should-i-interpret-the-output-of-density-tools/

pdf(file.path(version, 'Figures', paste0('Hotspots_by_Heading_unmapped', warning_keyword, '.pdf')), width = 10, height = 10)

foreach(idx = unique(d_ll_proj$route_id), .packages = c("dplyr", "ggmap", 'MASS', 'raster', 'sp', 'reshape')) %dopar% { 
  # idx = unique(d_ll_proj$route_id)[1]
  cat(idx, '\n')
  
  usedat = d@coords[ d@data$route_id == idx, ]
  
  # current area in square kilometers
  ( total_area_sqkm = diff(range(usedat[,1]))/1000 * diff(range(usedat[,2]))/1000 )
  
  # Make each grid cell 50 sq m. So each side needs to be sqrt(50) 
  # longitudinal count of grids to use:
  lon_n_use = ceiling(diff(range(usedat[,1])) / sqrt(50) )
  
  # latitudeinal count of grids to use:
  lat_n_use = ceiling(diff(range(usedat[,2])) / sqrt(50) )
  
  dens = kde2d(usedat[,1], usedat[,2],
               n = c(lon_n_use, lat_n_use),
               lims = c(range(d@coords[,1]), range(d@coords[,2])))
  
  
  # Values in each cell now represent count of warnings across the whole area, total_area_sqkm (15.79 sq km in this example). Let's turn this in to values per square mile.
  # Each grid cell is 50 sq m. So first divide by total area to get count per one square kilometer. Could then multiply by 0.386102 to get counts per square mile, or multiply by 1e6 (1 million) to get events per square meter
  
  dens$z = ( dens$z / total_area_sqkm ) * 1e6  
  
  # make color map with increasing transparency at lower range
  coln = 3*3 # make it divisible by 3 for following steps
  col1 = rev(heat.colors(coln, alpha = 0.2))
  col2 = rev(heat.colors(coln, alpha = 0.8))
  col3 = rev(heat.colors(coln, alpha = 0.9))
  
  col4 = c(col1[1:(coln/3)], col2[(coln/3+1):(2*coln/3)], col3[(1+2*coln/3):coln])
  
  image(dens, col = col4,
        main = idx)
  contour(dens, add = T)
  
  dens_col_cut = cut(dens$z, breaks = length(col4))
  levels(dens_col_cut)
  
  legend('topleft',
         fill = col4,
         legend = levels(dens_col_cut),
         title = "Density of events per square meter",
         cex = 0.5)
  
  # Make density raster into a spatial object
  dimnames(dens$z) = list(dens$x, dens$y)
  
  
  d_r <- rasterFromXYZ(reshape::melt(dens$z),
                       crs = proj)
  
  
  # http://openstreetmapdata.com/info/projections
  d_r_ll <- projectRaster(from = d_r,
                          crs = CRS(projargs = "+init=epsg:3857")) # Tranform to mercator lat long, to match stamen map base layers
  
  # Write out to spatial data layer for ArcMap work
  writeRaster(d_r_ll, filename = file.path('Raster', paste0("Raster_Unnormalized_All_", warning_keyword, '_', idx, ".tif")),
              format = 'GTiff')
  # in ArcMap: open GeoTIFF, change symbology as appropriate.
  
} # end loop over routes
dev.off()


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

summary(db$unique_ID %in% d$unique_ID)

# Subset db to only unique_ID which are present in individual warning data d
db <- db[db$unique_ID %in% d$unique_ID,]

# 700 trips out of 21k are dropped

# Simple query: how many trips were run for each route_name and heading?

june_trip_count = db %>%
  group_by(route_name, heading) %>%
  summarize(count = n()) %>%
  mutate(rte_head = make.names(paste(route_name, heading)))

# Now re-do the heat map, dividing by june_trip_count for each route name and heading combination

pdf(file.path(version, 'Figures', paste0('Hotspots_by_Heading_unmapped_normalized', warning_keyword, '.pdf')), width = 10, height = 10)

foreach(idx = unique(d_ll_proj$route_id), .packages = c("dplyr", "ggmap", 'MASS', 'raster', 'sp', 'reshape')) %dopar% { 
  # idx = unique(d_ll_proj$route_id)[1]
  cat(idx, '\n')
  
  usedat = d@coords[ d@data$route_id == idx, ]
  
  # current area in square kilometers
  ( total_area_sqkm = diff(range(usedat[,1]))/1000 * diff(range(usedat[,2]))/1000 )
  
  # Total study area in square kilometers
  ( total_area_sqkm = diff(range(d@coords[,1]))/1000 * diff(range(d@coords[,2]))/1000 )
  
  # Make each grid cell 50 sq m. So each side needs to be sqrt(50) 
  # longitudinal count of grids to use -- now use full study area instead of usedat lat longs
  lon_n_use = ceiling(diff(range(d@coords[,1])) / sqrt(50) )
  
  # latitudeinal count of grids to use (full study area):
  lat_n_use = ceiling(diff(range(d@coords[,2])) / sqrt(50) )
  
  # Adding lims to extend to the full study area
  
  dens = kde2d(usedat[,1], usedat[,2],
               n = c(lon_n_use, lat_n_use),
               lims = c(range(d@coords[,1]), range(d@coords[,2])))
  
  # Values in each cell now represent count of warnings across the whole area, total_area_sqkm (15.79 sq km for Dash F N, but 28.4 sq km for full study area). Let's turn this in to values per square mile.
  # Each grid cell is 50 sq m. So first divide by total area to get count per one square kilometer. Could then multiply by 0.386102 to get counts per square mile, or multiply by 1e6 (1 million) to get events per square meter
  
  dens$z = ( dens$z / total_area_sqkm ) * 1e6  
  
  # Now standardize by dividing by the total number of trips. Use the data frame june_trip_count.
  count_i = june_trip_count %>% ungroup() %>% filter(rte_head == idx) %>% dplyr::select(count)
  
  dens$z = dens$z / as.numeric(count_i)
  
  # make color map with increasing transparency at lower range
  coln = 3*3 # make it divisible by 3 for following steps
  col1 = rev(heat.colors(coln, alpha = 0.2))
  col2 = rev(heat.colors(coln, alpha = 0.8))
  col3 = rev(heat.colors(coln, alpha = 0.9))
  
  col4 = c(col1[1:(coln/3)], col2[(coln/3+1):(2*coln/3)], col3[(1+2*coln/3):coln])
  
  image(dens, col = col4,
        main = gsub("\\.", " ", idx))
  contour(dens, add = T)
  
  dens_col_cut = cut(dens$z, breaks = length(col4))
  
  legend('topleft',
         fill = col4,
         legend = levels(dens_col_cut),
         title = "Density of events per square meter, per trip",
         cex = 0.9)
  
  # Make density raster into a spatial object
  dimnames(dens$z) = list(dens$x, dens$y)
  
  d_r <- rasterFromXYZ(reshape::melt(dens$z),
                       crs = proj)
  
  # http://openstreetmapdata.com/info/projections
  d_r_ll <- projectRaster(from = d_r,
                          crs = CRS(projargs = "+init=epsg:3857")) # Tranform to mercator lat long, to match stamen map base layers
  
  # Write out to spatial data layer for ArcMap work
  writeRaster(d_r_ll, filename = file.path('Raster', paste0("Raster_Normalized_All_", warning_keyword, '_',idx, ".tif")),
              format = 'GTiff')
  # in ArcMap: open GeoTIFF, change symbology as appropriate.
} # end loop over routes

dev.off()



########################################################################################### Clustering ----
########################################################################################### Not currently running clustering, memory intensive on local 

# TODO: calculate clusters with better memory optimizing 

NOTRUN = T

if(NOTRUN){

# Cluster analysis ----

# Parameters:
min.cluster = 100 # minimum number of values in a cluster.


for(route in unique(d$route_id)){ # route = unique(d$route_id)[1]
  d.dist <- spDists(d[d$route_id == route,]) # spDists gives distance in km, increasing here to m. 55k observations too many for spDists all at once. Need to loop over routes.
  
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
  
  d.cut <- cutree(d.clust, k = 100)
  
  # Cluster names to not show, as these are below the minimum number of members:
  less.than.min = names(table(d.cut))[table(d.cut) <= min.cluster]
  
}

dc <- data.frame(d[d$route_id == route,], d.cut, lat = coordinates(d[d$route_id == route,])[,2], lon = coordinates(d[d$route_id == route,])[,1])

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

mm <- plotmap(lat = dc2$lat.m, lon = dc2$lon.m,
              pch = 21,
              bg = "purple",
              lwd = 2,
              cex = log(dc2$n/15, base = 2),
              col = "black",
              maptype = "roadmap"
)

legend("topleft",
       pt.bg = "purple",
       col = "black",
       pch = 21,
       pt.cex = c(1, 1.7, 2.8, 3.9, 5.1),#levels(cut(log(dc2$n/15, base = 2), 5))
       legend = plyr::round_any(15*(2^c(1, 1.7, 2.8, 3.9, 5.1)), 5),
       title = "No. incidents",
       y.intersp = 2,
       x.intersp = 2)

# Optional: show number of values in each cluster:
ShowVals = FALSE
if(ShowVals){
  TextOnStaticMap(mm, 
                  lat = dc2$lat.m, lon = dc2$lon.m,
                  add = T,
                  labels = paste("N =", dc2$n),
                  cex = 0.5
  )
}
dev.print(device = png, 
          width = 600,
          height = 600,
          file = paste0("Mapping_Route12_Clusters.png"))


# Convex Hulls ----
# Calculate hulls for each distinct set of points deterimined by the d.cut of the clustering.
# Loop over sets of points and apply the chull() function, then use this to create SpatialPolygons based on those values.

hulllist = list()
for(i in dc2$d.cut){ # i = 1
  cv <- chull(dc[c("lon","lat")][d.cut == i,])
  hulllist[[as.character(i)]] = Polygons(list(Polygon(dc[c("lon","lat")][d.cut == i,][cv,])), i)
}

ConvHullPoly <- SpatialPolygons(hulllist, proj4string = CRS(proj))

# First, show all convex hull polygons:

mm <- plotmap(lat = dc$lat, lon = dc$lon,
              pch = "+",
              cex = 0.8,
              col = alpha("grey20", 0.5),
              maptype = "road",
              zoom = 14)

PlotPolysOnStaticMap(mm, polys = ConvHullPoly, 
                     col = alpha("lightgreen", 0.5))

# Center on E. Madison and 17th and zoom in closer:

mm <- GetMap(center = c(47.615669, -122.310151),
             zoom = 17, GRAYSCALE = F,
             maptype = 'road'
)
PlotOnStaticMap(mm, lat = dc$lat, lon = dc$lon,
                pch = 21,
                bg = alpha("grey80", 0.8),
                cex = 0.8,
                col = alpha("grey20", 0.5))
PlotPolysOnStaticMap(mm, polys = ConvHullPoly, 
                     col = alpha("lightgreen", 0.8))
PlotOnStaticMap(mm, lat = dc$lat, lon = dc$lon,
                pch = 21,
                bg = alpha("grey80", 0.8),
                cex = 0.8,
                col = alpha("grey20", 0.5),
                add = T)

} # end NOTRUN
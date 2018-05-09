# Pedestrian conflict hot spot analysis
# Based on Mobileye data from vehicle in Seattle in April-June 2016
# Using 
# 1. Clustering
# 2. Kernal density using ks package or other

# To match the CrimeStat/ArcGIS approach by Don and Andy

# For each approach, make maps with satellite image overlays. Next step: Highlight bus stops, and look at associate between hot spots and bus stop.

# Setup ----
# If you don't have these packages: install.packages(c("maps", "sp","spatstat", "RgoogleMaps","ks","scales","tidyverse")) 
library(maps)
library(sp)
library(spatstat)
library(RgoogleMaps)
library(ks)
library(scales)
library(tidyverse)

setwd("M:/Helping/Fisher/Crimestat") # update as appropriate 

d <- read.csv("Route12Data041718.txt", stringsAsFactors = F, sep = "\t")

PLOTMAPS = F # Set to T to make individual maps by StatusName

# Summary of decisions from Don's writeup:
# Bounding box: 47.599011 / -122.339481
#               47.6341  / -122.303993

# Should cover 4.358 sq mi

# Neighbors: Nearest negibhro heierarchical spatial clustering and Random NN distance. 
# Search radius in 'middle notch'
# 1 SD for ellipses. 0 simulations. 10 points per cluster minimum. 

# Look at the data and reformat ----

summary(d)

# get date and time in the right format
d$time <- strptime(d$LocationTime, "%m/%d/%Y %H:%M:%S")
summary(d$time)

# trim trailing white space from all text fields
textfields <- c("VehicleName", "UnitID", "Address", "StatusName")
d[textfields] <- apply(d[textfields], 2, FUN = function(x) sub(" +$", "", x))

# Make it a spatial data frame, only picking out relevant columns
d <- SpatialPointsDataFrame(coords = d[c("Longitude","Latitude")], data = d[c("Address", "StatusName", "time")],
                            proj4string = CRS("+proj=longlat +datum=WGS84"))

# Get data frame for plotting 
dc <- data.frame(d@data, lat = coordinates(d)[,2], lon = coordinates(d)[,1])

# 1. Clusters ----

# Parameters:
min.cluster = 10 # minimum number of values in a cluster.

d.dist <- spDists(d, longlat = T)*1000 # spDists gives distance in km, increasing here to m 
d.clust <- hclust(as.dist(d.dist), method = "single") # average: linkage by unweighted pairwise group method with arithmatic mean, UPGMA. Change method to "single" for single linkage, see ?hclust for more options. Single linkage is likely the what Crimestat refers to as nearest neighbor

# cut the tree to make groupings
# Find the number of groupings which results in no less than 10 values in a cluster
# Search for correct k in a loop
min.cluster.members = 0
h = 1

while(min.cluster.members < min.cluster){
  d.cut <- cutree(d.clust, h = h)
  min.cluster.members = min(table(d.cut))
  h = h + 1
  print(data.frame(k, min.cluster.members))
  }
print(k)

dc <- data.frame(d@data, d.cut, lat = coordinates(d)[,2], lon = coordinates(d)[,1], m.of.d)

dc$time <- as.character(dc$time) # dplyr doesn't work well with date-time formats

# plot(as.dendrogram(d.clust))
# rect.hclust(d.clust, k = 10)

# aggregated by group and summarize. can add StatusName to group_by
dc2 <- dc %>%
  group_by(d.cut) %>%
  summarize(lat.m = mean(lat),
            lon.m = mean(lon),
            lat.sd = sd(lat),
            lon.sd = sd(lon),
            n = n(),
            time = mean(m.of.d),
            time.sd = sd(m.of.d)
  )

mm <- plotmap(lat = dc2$lat.m, lon = dc2$lon.m,
              pch = 21,
              bg = "grey80",
              lwd = 2,
              cex = dc2$n/50,
              col = "red",
              maptype = "roadmap"
)

TextOnStaticMap(mm, 
                lat = dc2$lat.m, lon = dc2$lon.m,
                add = T,
                labels = paste("N =", dc2$n),
                cex = 0.5
)

dev.print(device = png, 
          width = 600,
          height = 600,
          file = paste0("Mapping_Route12_Clusters.png"))


# 2. Kernal density ----

# Settings
kern = "epanechnikov" #  "gaussian" # options to try: gaussian, epanechnikov, quartic and disc
bwidth = 0.5 # betwen 0 and 1
dataset = "all" # options: all, weekend, am, pm

par.reset = par(no.readonly = T)

# Get a map for plotting. Save as object "mm", which we will use for convertting lat longs into plottable points 

mm <- plotmap(lat = dc$lat, lon = dc$lon,
              pch = 1,
              col = alpha("white", 0),
              maptype = "roadmap")

# Convert from lat long to plot-able XY for mapping.

ll <- LatLon2XY.centered(mm, lat = coordinates(d)[,2], lon = coordinates(d)[,1])

if(dataset == "Weekend") {
      selector = format(dc$time, "%u") %in% c(6, 0) # weekday as decimal number, 0-6, Sunday is 0. Compare with %a
      ll <- LatLon2XY.centered(mm, lat = coordinates(d)[,2][selector], lon = coordinates(d)[,1][selector])
      if(!any(selector)) stop("No weekend days in this selection")
      }

if(dataset == "am") {
    selector = format(dc$time, "%p") == "AM" #  AM/PM 
    ll <- LatLon2XY.centered(mm, lat = coordinates(d)[,2][selector], lon = coordinates(d)[,1][selector])
    if(!any(selector)) stop("No morning times in this selection")
    }


if(dataset == "pm") {
    selector = format(dc$time, "%p") == "PM" # AM/PM 
    ll <- LatLon2XY.centered(mm, lat = coordinates(d)[,2][selector], lon = coordinates(d)[,1][selector])
    if(!any(selector)) stop("No evening times in this selection")
    }

# See ?kde. Normal kernel is default
dl <- data.frame(ll$newX, ll$newY)
dd <- kde(x = dl,
          H = Hscv(dl),
          adj.positive = 0.25)

# Plotting ----
mm <- plotmap(lat = dc$lat, lon = dc$lon,
              pch = "+",
              cex = 0.8,
              col = alpha("grey20", 0.05),
              maptype = "roadmap")

plot(dd, add = T, 
     drawpoints = F,
     display = "filled.contour")

# Get the contour levels
levs <- contourLevels(dd, prob = c(0.25, 0.5, 0.75))
contcut <- cut(dd$cont, breaks = levs)
# select the first instance of each contour level
colordf <- data.frame(contcut, heat.colors(99))
legcol <- colordf[!duplicated(colordf[,1]),]

legend("topleft",
       title = "Density",
       legend = legcol$contcut,
       fill = as.character(legcol$heat.colors.99))

# Pixel values are estimated intensity values, expressed in "points per unit area".

legend("top", legend = paste(toupper(dataset), kern, bwidth))

dev.print(device = png, 
          width = 600,
          height = 600,
          file = paste0(paste("Mapping_Rt12", kern, bwidth, dataset, sep = "_"), ".png"))

plot(dd); dev.print(device = png, 
                   width = 600,
                   height = 600,
                   file = paste0(paste("Unmapped", kern, bwidth, dataset, sep = "_"), ".png"))

# Difference between am / pm intensities ----

selector = format(dc$time, "%p") == "AM" #  AM/PM 
ll <- LatLon2XY.centered(mm, lat = coordinates(d)[,2][selector], lon = coordinates(d)[,1][selector])
dp <- ppp(ll$newX, ll$newY, window = pwin)
dd.am <- density(dp, kernel = kern, adjust = bwidth, edge = T)

selector = format(dc$time, "%p") == "PM" # AM/PM 
ll <- LatLon2XY.centered(mm, lat = coordinates(d)[,2][selector], lon = coordinates(d)[,1][selector])
dp <- ppp(ll$newX, ll$newY, window = pwin)
dd.pm <- density(dp, kernel = kern, adjust = bwidth, edge = T)

dd.diff <- dd.pm - dd.am

par(par.reset)
plot(dd.diff, main = paste("PM - AM densities \n", kern, bwidth))
dev.print(device = png, 
          width = 600,
          height = 600,
          file = paste0(paste("Unmapped_PM-AM", kern, bwidth, sep = "_"), ".png"))


# titleloc <- XY2LatLon(mm, 2.221, 277.31) # use locator() to find where to put title
# TextOnStaticMap(mm, lat = titleloc[1], lon = titleloc[2], 
#                 paste(dataset, kern, bwidth), 
#                 add = T, pch = 2,
#                 font = 2)

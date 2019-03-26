# Pedestrian conflict hot spot analysis
# Based on Mobileye data from vehicle in Seattle in April-June 2016
# Using 
# 2. Kernal density using ks package or other

# For each approach, make maps with satellite image overlays. Next step: Highlight bus stops, and look at associate between hot spots and bus stop.

# Figures to make:
# Weekend, weekday
# Daylight, non-daylight (should not be many)
# Overall
# 
# Make difference plots 
# 
# Bandwidth: within 100'? 4 lane intersection is ~ 50' wide
# Use all warnings for now

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

d <- read.csv("Route 12 data.csv", stringsAsFactors = F)

PLOTMAPS = F # Set to T to make individual maps by StatusName

# Look at the data and reformat ----

summary(d)

# get date and time in the right format
d$time <- strptime(d$LocationTime, "%m/%d/%Y %H:%M:%S")
summary(d$time)

# trim trailing white space from all text fields
textfields <- c("VehicleName", "UnitID", "Address", "StatusName")
d[textfields] <- apply(d[textfields], 2, FUN = function(x) sub(" +$", "", x))

# Make it a spatial data frame, only picking out relevant columns
d <- SpatialPointsDataFrame(coords = d[c("Longitude","Latitude")], data = d[c("Address", "StatusName", "time")])

# Get data frame for plotting 
dc <- data.frame(d@data, lat = coordinates(d)[,2], lon = coordinates(d)[,1])

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

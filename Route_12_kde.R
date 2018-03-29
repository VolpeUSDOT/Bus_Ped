# Pedestrian conflict hot spot analysis
# Based on Mobileye data from vehicle in Seattle in April-June 2016

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

# change f to higher value to extend the range of the observation window. Use the same observation window for all subsets of data.
pwin = owin(xrange = extendrange(range(ll$newX), f = 0.2), 
            yrange = extendrange(range(ll$newY), f = 0.2))

# Use the "point pattern process" ppp function from spatstat, using the observation window as the range in which these points occur. Defining the observation window is an important step, see ?ppp. Points must lie inside the window. 
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


dp <- ppp(ll$newX, ll$newY, window = pwin) # warning about duplicate points, double-check to make sure these are true duplicates

# See ?density.ppp
dd <- density(dp,
              kernel = kern,
              adjust = bwidth, # use this to change the bandwidth
              edge = T, # adjustment for edge of observation window, recommend T
              at = "pixels") # change to "points" to get the density exactly for each point

# Define the color map:
# make color map with increasing transparency at lower range
coln = 3*25 # make it divisible by 3 for following steps
col1 = rev(heat.colors(coln, alpha = 0.2))
col2 = rev(heat.colors(coln, alpha = 0.8))
col3 = rev(heat.colors(coln, alpha = 0.9))

col4 = c(col1[1:coln/3], col2[(coln/3+1):(2*coln/3)], col3[(1+2*coln/3):coln])

pc <- colourmap(col = col4, 
                range = range(dd))

# Plotting ----
mm <- plotmap(lat = dc$lat, lon = dc$lon,
              pch = "+",
              cex = 0.8,
              col = alpha("grey20", 0.05),
              maptype = "roadmap")
plot(dd, add = T, col = pc)

# Get the contour levels
levs <- quantile(dd, c(0.85, 0.95, 0.99, 1))
# select the color for of each contour level
legcol <- pc(levs)

# Pixel values are estimated intensity values, expressed in "points per unit area".

legend("topleft",
       title = "Density",
       legend = round(levs, 4),
       fill = legcol)

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

# Pedestrian conflict hot spot analysis
# Based on Mobileye data from vehicle in Seattle in April-June 2016
# Using 
# 1. Clustering with hclust and cluster package
# 2. Kernal density using spatstat or ks package

# 5.1 Setup ----
# If you don't have these packages: install.packages(c("maps", "sp","spatstat", "RgoogleMaps","ks","scales","tidyverse","cluster")) 
library(maps)
library(sp)
library(spatstat)
library(RgoogleMaps)
library(ks)
library(scales)
library(tidyverse)
library(rgdal)
library(cluster)

# Set working directory and read in data
#setwd("~/Documents/Work/Volpe/KDE") # update as appropriate 
setwd("M:/Helping/Fisher/Crimestat") # update as appropriate 

d <- read.csv("Route12Data041718.txt", stringsAsFactors = F, sep = "\t")

# Look at the data and reformat

summary(d)

# Get date and time in the right format
d$time <- strptime(d$LocationTime, "%m/%d/%Y %H:%M:%S")
summary(d$time)

# Trim trailing white space from all text fields
textfields <- c("VehicleName", "UnitID", "Address", "StatusName")
d[textfields] <- apply(d[textfields], 2, FUN = function(x) sub(" +$", "", x))

# Make it a spatial data frame, only picking out relevant columns
d <- SpatialPointsDataFrame(coords = d[c("Longitude","Latitude")], data = d[c("Address", "StatusName", "time")],
                            proj4string = CRS("+proj=longlat +datum=WGS84"))

# use albers equal area projection
proj <- showP4(showWKT("+init=epsg:102008"))
d.proj <- spTransform(d, CRS(proj))

# Get data frame for plotting 
dc <- data.frame(d@data, lat = coordinates(d)[,2], lon = coordinates(d)[,1])

# 5.2 Cluster analysis ----

# Parameters:
min.cluster = 10 # minimum number of values in a cluster.

d.dist <- spDists(d, longlat = T)*1000 # spDists gives distance in km, increasing here to m 
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

dc <- data.frame(d@data, d.cut, lat = coordinates(d)[,2], lon = coordinates(d)[,1])

dc$time <- as.character(dc$time) # dplyr doesn't work well with date-time formats, so convert to text here.

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
# 5.3 Kernal density ----

# Settings
kern = "gaussian" # Kernel to use
bwidth = 0.2 # between 0 and 1

par.reset = par(no.readonly = T)

# Get a map for plotting. Save as object "mm", which we will use for converting lat longs into plottable points 
mm <- plotmap(lat = dc$lat, lon = dc$lon,
              pch = 1,
              col = alpha("white", 0),
              maptype = "roadmap")

# Convert from lat long to plot-able XY for mapping.

ll <- LatLon2XY.centered(mm, lat = coordinates(d)[,2], lon = coordinates(d)[,1])

# Can change f to higher value to extend the range of the observation window. Use the same observation window for all subsets of data.
pwin = owin(xrange = extendrange(range(ll$newX), f = 0.2), 
            yrange = extendrange(range(ll$newY), f = 0.2))

# Or manually set the observation window, following the CrimeStat approach
ll.owin <- LatLon2XY.centered(mm, lat = c(47.599011, 47.635341), 
                             lon = c(-122.339481, -122.303993))

pwin = owin(xrange = range(ll.owin$newX), yrange = range(ll$newY))

dp <- ppp(ll$newX, ll$newY, window = pwin) 

# See ?density.ppp
dd <- density(dp,
              kernel = kern,
              adjust = bwidth, # use this to change the bandwidth
              edge = T, # adjustment for edge of observation window, recommend T
              at = "pixels") # change to "points" to get the density exactly for each point

# Define the color map:
# make color map with increasing transparency at lower range
coln = 5*25 # make it divisible by 3 for following steps
col1 = rev(heat.colors(coln, alpha = 0.2))
col2 = rev(heat.colors(coln, alpha = 0.8))
col3 = rev(heat.colors(coln, alpha = 0.9))

col4 = c(col1[1:coln/3], col2[(coln/3+1):(2*coln/3)], col3[(1+2*coln/3):coln])

pc <- colourmap(col = col4, 
                range = range(dd))

# Or, use color map to match CrimeStat
use.breaks = quantile(dd, probs = c(0.9, 0.95, 0.975, 0.99, 0.999, 1))
pc <- colourmap(col = c(alpha("white",0.1),
                alpha("yellow", 0.5),
                alpha("red", 0.6),
                alpha("purple", 0.7),
                alpha("blue", 0.7)),
                breaks = use.breaks)


# Plotting Kernel Density ----
mm <- plotmap(lat = dc$lat, lon = dc$lon,
              pch = 1,
              col = alpha("white", 0),
              maptype = "roadmap")

plot(dd, add = T, col = pc)

# Get the contour levels
# select the color for of each contour level
legcol <- pc(use.breaks)

# Pixel values are estimated intensity values, expressed in "points per unit area".
legend("topleft",
       title = "Density",
       legend = round(use.breaks, 4),
       fill = legcol)

plot(dd); dev.print(device = png, 
                   width = 600,
                   height = 600,
                   file = paste0(paste("Unmapped", kern, bwidth, dataset, sep = "_"), ".png"))

# Combine kernel density, convex hulls, and points in zoomed in map.
# Make a high resoltion map and zoom in by cropping


mm <- plotmap(lat = dc$lat, lon = dc$lon,
              pch = 1,
              col = alpha("white", 0),
              maptype = "roadmap")

# pdf("OverlayMap.pdf", width = 20, height = 20) # uncomment for PDF
mm <- GetMap.bbox(lonR = range(dc$lon),
                  latR = range(dc$lat),
            zoom = 14,
            SCALE = 2,
             maptype = 'road'
             )

PlotOnStaticMap(mm, lat = dc$lat, lon = dc$lon,
              pch = 21,
              bg = alpha("grey80", 0.8),
              cex = 0.8,
              col = alpha("grey20", 0.5))
PlotPolysOnStaticMap(mm, polys = ConvHullPoly, 
                     col = alpha("lightgreen", 0.8))

spatstat::plot.im(dd, col = pc, add = T)
# dev.off() # uncomment for PDF output

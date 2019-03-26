# Pedestrian conflict hot spot analysis
# Based on Mobileye data from vehicle in Seattle in April-June 2016

# 1. Cluster using Euclidean distance + Nearest-neighbor linkage (dist + hclust)
# 2. Kernal density estimtion using ks package or other (see Route_12_kde.R)

# For each approach, make maps with satellite image overlays. Highlight bus stops, and look at associate between hot spots and bus stops.

# Questions: do we care about the time variable? If not, can simplify to a hot spot analysis across time. If so, want to loop this over the time period of interest (day, week, month; weekend, weekday); can then look at differences in incident densities between time points.
# Also, do we care about "StatusName" type? 

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
library(maps)
library(sp)
library(RgoogleMaps)
library(ks)
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

# 1. Clustering ----

# Plot all, by StatusName 

if(PLOTMAPS) {
pointcols <- rainbow(n = length(unique(d$StatusName)), v = 0.9, start = 0.7, end = .1, alpha = 0.25)

for(i in 1:length(unique(d$StatusName))){
  dx = d[d$StatusName == unique(d$StatusName)[i],]
  

  plotmap(lat = coordinates(dx)[,2], lon = coordinates(dx)[,1],
          #zoom = 13,
          pch = "+",
          cex = 2,
          col = pointcols[i],
          maptype = "roadmap"
          )
  
   title(main = paste("\n", unique(d$StatusName)[i]))
  
  dev.print(device = png, 
            width = 600,
            height = 600,
            file = paste0("Mapping_Route12_", unique(d$StatusName)[i], ".png"))
  
  }
}
# Make clusters by spatial and temporal proximity

d.dist <- spDists(d, longlat = T)*1000 # spDists gives distance in km, increasing here to m 
# minute of day
m.of.d <- rowSums(data.frame(
                  as.numeric(format(d$time, "%H")),
                  as.numeric(format(d$time, "%M"))/60,
                  as.numeric(format(d$time, "%S"))/3600))

d.temp <- as.matrix(dist(m.of.d)) # distance matrix by time. This is difference in minutes by time of day (i.e., ignoring date, just looking within each day). Need to correctly account for 24h time; currently 00:00 is max different from 23:59

d.dt <- d.dist * d.temp # dim(d.dt) # consider scaling to give equal weight to location and time 

d.clust <- hclust(as.dist(d.dist), method = "average") # linkage by unweighted pairwise group method with arithmatic mean, UPGMA. Change method to "single" for single linkage, see ?hclust for more options. 

# Alternative: k-means clustering, using kmeans()

# cut the tree to make groupings

d.cut <- cutree(d.clust, k = 10) # return the 10 top level groups.

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




# Clustering and KDE for Don's 3-cluster example


# Setup ----
library(maps)
library(sp)
library(car) # for ellipse
library(RgoogleMaps) # for plotmap and 
library(ks)
library(tidyverse)

setwd("M:/Helping/Fisher/Crimestat") # update as appropriate 

d <- read.csv("don three clusters __ 3 21 18.csv", stringsAsFactors = F)

# make sure all longitudes are negative, for Western hemisphere

d$Long[d$Long > 0] <- -1*d$Long[d$Long > 0]

# Add some variation in longtidues

d$Long <- d$Long + runif(nrow(d), min = -0.001, max = 0.001)

head(d);tail(d);summary(d)

# Make it a spatial data frame, only picking out relevant columns
d <- SpatialPointsDataFrame(coords = d[c("Long","Lat")], data = d[c("Name")])

# Clustering ----

d.dist <- spDists(d, longlat = T)*1000 # spDists gives distance in km, increasing here to m 
d.clust <- hclust(as.dist(d.dist), method = "single") # "average" = linkage by unweighted pairwise group method with arithmatic mean, UPGMA. Change method to "single" for single linkage, see ?hclust for more options. 

d.cut <- cutree(d.clust, k = 3) # return the 3 top level groups.

dc <- data.frame(d@data, d.cut, lat = coordinates(d)[,2], lon = coordinates(d)[,1])

# par(mar = c(10, 2, 3, 2))
#  plot(as.dendrogram(d.clust))
#  rect.hclust(d.clust, k = 3)

# aggregated by group and summarize. can add StatusName to group_by
dc2 <- dc %>%
  group_by(d.cut) %>%
  summarize(lat.m = mean(lat),
            lon.m = mean(lon),
            lat.sd = sd(lat),
            lon.sd = sd(lon),
            lat.90.half = quantile(lat, 0.90)-quantile(lat, 0.50),
            lon.90.half = quantile(lon, 0.90)-quantile(lon, 0.50),
            n = n()
  )

zoom = 14

mm <- plotmap(lat = dc2$lat.m, lon = dc2$lon.m,
              lwd = 0,
              zoom = zoom,
              maptype = "roadmap")


for(i in 1:nrow(dc2)){
  
  dcx <- dc[dc$d.cut == i,]
  
  ll <- LatLon2XY.centered(mm, lat = dcx$lat, lon = dcx$lon)
  
  points(ll$newX, ll$newY, pch = "+")
  
  E <- dataEllipse(ll$newX, ll$newY,
                   levels = 0.9,
                   plot.points = F,
                   add = T)
  }

dev.print(device = png, 
          width = 600,
          height = 600,
          file = paste0("Mapping_Don3_Clusters.png"))


### Scratch
# 
# TextOnStaticMap(mm, 
#                 lat = dc2$lat.m, lon = dc2$lon.m,
#                 add = T,
#                 labels = paste("N =", dc2$n),
#                 cex = 1
# )

# m <- GetMap.bbox(lonR = bbox(d)[1,],
#             latR = bbox(d)[2,],
#             size = c(640, 640),
#             zoom = zoom,
#             SCALE = 2,
#             destfile = "bgmap.png",
#             GRAYSCALE = T)
# 
# library(png)
# ima <- readPNG("bgmap.png")
# 
# plot(x = bbox(d)[1,],
#      y = bbox(d)[2,],
#      type = "n")
# 
# lim <- par()
# rasterImage(ima, lim$usr[1], lim$usr[3], lim$usr[2], lim$usr[4])
# # grid()

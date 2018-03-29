# Clustering and KDE for Don's 3-cluster example


# Setup ----
library(maps)
library(sp)
library(car) # for ellipse
library(RgoogleMaps) # for plotmap 
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

# KDE ----
library(spatstat)
# Need to define the observation window "owin" and make a point pattern process "ppp" from the lat-long points
class(d)


# Convert from lat long to plot-able XY for mapping

ll <- LatLon2XY.centered(mm, lat = coordinates(d)[,2], lon = coordinates(d)[,1])

# change f to higher value to extend the range of the observation window
pwin = owin(xrange = extendrange(range(ll$newX), f = 0.3), 
            yrange = extendrange(range(ll$newY), f = 0.3))


dp <- ppp(ll$newX, ll$newY, window = pwin)
# class(dp)

dd <- density(dp,
              kernel = "gaussian",
              adjust = 0.8, # use this to change the bandwidth
              edge = T, # adjustment for edge of observation window, recommend T
              at = "pixels") # change to "points" to get the density exactly for each point

mm <- plotmap(lat = dc$lat, lon = dc$lon,
              pch = "+",
              lwd = 0,
              zoom = zoom,
              maptype = "roadmap")

# Define the color map:
# library(scales); alpha(c("white", "blue", "red"), 0.5)

# rev(heat.colors(15, alpha = 0.5))
# make color map with increasing transparency at lower range
coln = 3*25 # make it divisible by 3 for following steps
col1 = rev(heat.colors(coln, alpha = 0.2))
col2 = rev(heat.colors(coln, alpha = 0.5))
col3 = rev(heat.colors(coln, alpha = 0.6))

col4 = c(col1[1:coln/3], col2[(coln/3+1):(2*coln/3)], col3[(1+2*coln/3):coln])

pc <- colourmap(col = col4, 
                       range = range(dd))

plot(dd, add = T, col = pc)

# Get the contour levels
levs <- quantile(dd, c(0.75, 0.9, 0.95, 1))
# select the color for of each contour level
legcol <- pc(levs)


legend("topleft",
       title = "Density",
       legend = round(levs, 4),
       fill = legcol)

dev.print(device = png, 
          width = 600,
          height = 600,
          file = paste0("Mapping_Don3_Clusters_Density.png"))


# Re-do with kde function from ks package

library(ks)

fhat <- kde(x = data.frame(ll$newX, ll$newY))
#fhat <- kde(x = data.frame(dc$lat, dc$lon))

plotmap(lat = dc$lat, lon = dc$lon,
              pch = "+",
              lwd = 0,
              zoom = zoom,
              maptype = "roadmap")

plot(fhat, add = T,
     drawpoints = F,
     display = "filled.contour"
     )

# Get the contour levels
levs <- contourLevels(fhat)
contcut <- cut(fhat$cont, breaks = levs)
# select the first instance of each contour level
colordf <- data.frame(contcut, heat.colors(99))
legcol <- colordf[!duplicated(colordf[,1]),]

legend("topleft",
       title = "Density",
       legend = legcol$contcut,
       fill = as.character(legcol$heat.colors.99)
       )


dev.print(device = png, 
          width = 600,
          height = 600,
          file = paste0("Mapping_Don3_Clusters_KDE.png"))

plot(fhat, add = F,
      display = "persp",
     xlab = "Longitude",
     ylab = "Latitude",
     zlab = "Density"
)

dev.print(device = png, 
          width = 600,
          height = 600,
          file = paste0("Mapping_Don3_Clusters_KDE_3d.png"))

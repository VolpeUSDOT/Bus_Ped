# 

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
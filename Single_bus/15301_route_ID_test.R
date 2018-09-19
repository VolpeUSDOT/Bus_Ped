# Mapping bus routes for LADOT, and attempting to identify which route was being traveled on which day by bus 15301

# setup ----
library(rgdal)
library(tidyverse)

setwd("//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data")

load('Warning_Braking_15301.RData')

# Read in Downtown DASH routes
dt_dash <- readOGR(file.path(getwd(), "Routes"), layer = "Downtown_DASH_Routes")

# Explore routes and warnings ----

# plot(dt_dash)
# dt_dash@data # five routes.

# Plot routes and hard braking, for example.

pdf("../Figures/Downtown_DASH+Braking.pdf",
    width = 8.5, height = 11)

colz = rainbow(nrow(dt_dash@data), alpha = 0.5)

plot(dt_dash[dt_dash@data$RouteNameS == "A",],
     col = colz[1],
     lwd = 2.5,
     ylim = as.vector(bbox(dt_dash)["y",]),
     xlim = as.vector(bbox(dt_dash)["x",])
     )

for(i in 2:nrow(dt_dash@data)){
  plot(dt_dash[dt_dash@data$RouteNameS == dt_dash@data$RouteNameS[i],],
       col = colz[i],
       add = T,
       lwd = 2.5
  )
  }

# Add hard braking
b_df <- b; class(b_df) = 'data.frame'

b_s <- SpatialPointsDataFrame(coords = b_df[c("Longitude", "Latitude")],
                              data = b_df)

plot(b_s[b_s@data$StatusName=="Safety - Braking - Aggressive",], add = T,
     pch = "+")


plot(b_s[b_s@data$StatusName=="Safety - Braking - Dangerous",], add = T,
     pch = 15)

# Legend

legend("topleft",
       col = c(colz, 1,1),
       pch = c(rep(NA, 5), 3, 15),
       legend = c(as.character(dt_dash$RouteName), "Aggressive Braking", "Dangerous Braking"),
       lwd =c(rep(2.5, 5), NA, NA),
       title = "Downtown DASH + Braking")
dev.off()

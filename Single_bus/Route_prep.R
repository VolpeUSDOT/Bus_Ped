# Prepping route data for LADDOT buses. This runs as part of Event_Route_Association.Rmd to generate a .RData file containing the bus routes from three systems: Community DASH, Downtown DASH, and Metro Bus lines.
library(rgdal)

codeloc = "~/git/Bus_Ped/Single_bus"
rootdir <- "//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data"
setwd(rootdir)

# Read in Downtown DASH routes
dt_dash <- readOGR(file.path(getwd(), "Routes"), layer = "Downtown_DASH_Routes")

# Read in Community DASH routes
co_dash <- readOGR(file.path(getwd(), "Routes"), layer = "Community_DASH_Routes")

# Read in Metro Bus routes
metro <- readOGR(file.path(getwd(), "Routes"), layer = "Metro_Bus_Lines")

# Need to ensure projections are identical for all three
stopifnot(all(identical(proj4string(metro), proj4string(co_dash)), 
              identical(proj4string(dt_dash), proj4string(co_dash))))

proj <- proj4string(dt_dash)

dt_dash <- spTransform(dt_dash, CRS(proj))
co_dash <- spTransform(co_dash, CRS(proj))
metro <- spTransform(metro, CRS(proj))

save(list = c("dt_dash", "co_dash", "metro", "proj"), file="LADOT_routes.RData")
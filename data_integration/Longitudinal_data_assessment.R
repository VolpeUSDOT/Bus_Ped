# Longitudinal work

library(tidyverse)
library(rgdal)
library(rgeos) # for gDistance
library(DBI) # to query sqlite database
library(RSQLite)
library(ggmap)

# Load data ----

# <><><><><><><><><><><><><><><><><><><><>
codeloc = "~/git/Bus_Ped/Single_bus"
rootdir <- "//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data/"
Database = "ituran_synchromatics_data.sqlite" # select version of database to use
# <><><><><><><><><><><><><><><><><><><><>

setwd(rootdir)
version = paste(gsub("\\.sqlite", "", Database), 'version', sep = '_')
system(paste('mkdir -p', version))
system(paste('mkdir -p', file.path(version, 'Figures')))

if(length(grep('LADOT_routes.RData', dir())) == 0) {
  source(file.path(codeloc, "Route_prep.R")) 
} else { 
  if(!exists("dt_dash")) load("LADOT_routes.RData") 
}
# Query hotspot table in database
conn = dbConnect(RSQLite::SQLite(), file.path("Data Integration", Database))
db = dbGetQuery(conn, "SELECT * FROM longitudinal_data_product")

# write.csv(db, file = 'Ituran_Data_Longitudinal.csv', row.names=F)

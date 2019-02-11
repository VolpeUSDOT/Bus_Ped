# Query hotspot data. Quick check in R, do actual work in Python.

dbwd = "//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data/Data Integration"

setwd(dbwd)

library(DBI)
library(RSQLite) # install.packages('RSQLite')
conn = dbConnect(RSQLite::SQLite(), "ituran_synchromatics_data.sqlite")

dbGetQuery(conn, "SELECT COUNT(*) FROM longitudinal_data_product")

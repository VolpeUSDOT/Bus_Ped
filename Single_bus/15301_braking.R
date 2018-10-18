# Ituran 2018 Bus 15301 -- hard braking

# Setup ----

library(tidyverse)
library(readxl)
library(lubridate)

setwd("//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data")

# Now, data are already prepared, just load this file:
load('Warning_Braking_15301.RData')

# Data prep (can skip now): First, read in all event data

#d <- readxl::read_excel("15301_2018_Jan-Aug.xlsx") # was truncating lat/long digits
d <- read.csv("15301_Jan-Aug_2018_Events.csv", stringsAsFactors = F)

makenum <- c("DistanceInMiles", "Odometer","Speed","Latitude","Longitude")
for(i in makenum) {d[,i] <- as.numeric(d[,i])}

# Date time format
dlt <- strptime(d$LocationTime, "%m/%d/%Y %H:%M:%S")
# Check it
data.frame(d$LocationTime, dlt)[sample(1:length(dlt), 15),]
# Replace with correct format
d$LocationTime = dlt
d$day = as.numeric(format(d$LocationTime, "%j"))
d$week = isoweek(d$LocationTime)
d$month = as.numeric(format(d$LocationTime, "%m"))
d$hour = as.numeric(format(d$LocationTime, "%H"))

# Now read in hard braking data
#b <- readxl::read_excel("Hard braking bus 15301.xlsx")
b <- read.csv("Hard braking bus 15301.csv", stringsAsFactors = F)

makenum <- c("DistanceInMiles", "Odometer","Speed","Latitude","Longitude")
for(i in makenum) {d[,i] <- as.numeric(d[,i])}

# Date time format
dlt <- strptime(b$LocationTime, "%m/%d/%Y %H:%M:%S")
# Check it
data.frame(b$LocationTime, dlt)[sample(1:length(dlt), 15),]
# Replace with correct format
b$LocationTime = dlt

# Extract day of year, week of year, and month as vectors
b$day = as.numeric(format(b$LocationTime, "%j"))
b$week = isoweek(b$LocationTime)
b$month = as.numeric(format(b$LocationTime, "%m"))
b$hour = as.numeric(format(b$LocationTime, "%H"))

# Join the two together, so we can have most accurate Odometer readings within a day
keepcol = c("LocationTime", "VehicleName", "Heading", "DistanceInMiles", "Odometer",
            "Address", "Speed", "StatusName", "Latitude", "Longitude","day","week","month","hour")

db <- rbind(d[keepcol], b[keepcol])
db <- db[order(db$LocationTime, db$Odometer, db$StatusName),]

save(list = c('d', 'b', 'db'), file = "Warning_Braking_15301.RData")
write.csv(db, file = "Warning_Braking_15301.csv", row.names=F)

# Time series ----

# Plot events by raw, and smoothed by week

# Need to drop Posix date time to use group_by and related functions
d_g <- db
d_g$LocationTime = as.character(d_g$LocationTime)

d_g_count <- d_g %>% 
  group_by(day, StatusName) %>%
  count()

d_g_miles <- d_g %>% 
  group_by(day) %>%
  summarize(miles = max(Odometer, na.rm=T) - min(Odometer, na.rm=T))

ggplot(d_g_miles) +
  geom_histogram(aes(x = miles), bins = 50, col = "grey") +
  ggtitle("Miles = max(Odometer) - min(Odometer)") +
  xlab("Miles") +
  ylab("Frequency")

ggsave("../Figures/Joint_Warning_Braking_Frequency_miles_per_day_Odometer_15301.jpg", device = "jpeg")

count_miles <- left_join(d_g_count, d_g_miles, by = "day")

# usewarnings = c('PDZ-R', 'PDZ-LR', 'ME - Pedestrian In Range Warning', 'PCW-LR', 'PCW-RR', 'ME - Pedestrian Collision Warning', 'PDZ - Left Front', 'PCW-LF')

usewarnings = c("Safety - Braking - Aggressive", "Safety - Braking - Dangerous")

count_miles <- count_miles %>%
  mutate(per_mile = n / miles) %>%
  filter(StatusName %in% usewarnings)

ggplot(count_miles %>% filter(miles > 10) ) +
  geom_line(aes(x = day, y = per_mile)) + 
  facet_wrap(~StatusName) +
  ggtitle("Brakin events per mile (minimum 10 miles), by day")

ggsave("../Figures/Braking_per_mile_15301.jpg", device = "jpeg")

ggplot(count_miles %>% filter(miles > 10)) +
  geom_histogram(aes(x = n), color = "grey", bins = 50) + 
  facet_wrap(~StatusName) + 
  ggtitle("Frequency of braking events per day (minimum 10 miles), by Status Name")

ggsave("../Figures/Distributions_braking_events_15301.jpg", device = "jpeg")

# By week of year

d_g_count <- d_g %>% 
  group_by(week, StatusName) %>%
  count()

d_g_miles <- d_g %>% 
  group_by(day) %>%
  summarize(miles = max(Odometer, na.rm = T) - min(Odometer, na.rm=T),
            week = max(week, na.rm = T)) %>%
  group_by(week) %>%
  summarize(week_miles = sum(miles))

count_miles <- left_join(d_g_count, d_g_miles, by = "week")

count_miles <- count_miles %>%
  mutate(per_mile = n / week_miles) %>%
  filter(StatusName %in% usewarnings)

ggplot(count_miles %>% filter(week_miles > 100)) +
  geom_line(aes(x = week, y = per_mile), size = 1) + 
  facet_wrap(~StatusName) +
  ggtitle("Braking events per mile, by week (mimimum 100 miles)")

ggsave("../Figures/Braking_events_per_mile_by_week_15301.jpg", device = "jpeg")

ggplot(count_miles %>% filter(week_miles > 100)) +
  geom_histogram(aes(x = n), color = "grey", bins = 50) + 
  facet_wrap(~StatusName) + 
  ggtitle("Frequency of braking events per week (minimum 100 miles), by Status Name")

ggsave("../Figures/Distributions_braking_events_by_week_15301.jpg", device = "jpeg")



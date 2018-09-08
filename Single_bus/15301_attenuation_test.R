# Ituran 2018 Bus 15301 test

# Setup ----

library(tidyverse)
library(readxl)
library(lubridate)

# wd  <- gsub  ( "\\\\",  "/",  readClipboard ()  ) # convert Windows slashes to forward

setwd("//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data")

d <- readxl::read_excel("15301_2018_Jan-Aug.xlsx")

# Date time format

dlt <- strptime(d$LocationTime, "%m/%d/%Y %H:%M:%S")
# Check it
data.frame(d$LocationTime, dlt)[sample(1:length(dlt), 15),]

# Replace with correct format

d$LocationTime = dlt

# Extract day of year, week of year, and month as vectors

d$day = as.numeric(format(d$LocationTime, "%j"))

d$week = isoweek(d$LocationTime)

d$month = as.numeric(format(d$LocationTime, "%m"))

# Mapping ----

# See Tableau workbook for now

# Time series ----

# Plot events by raw, smoothed by week, smoothed by month

# One version: by day, sum the odometer and count number of each StatusName in that day
# Need to drop Posix date time to use group_by and related functions
d_g <- d
d_g$LocationTime = as.character(d_g$LocationTime)

d_g_count <- d_g %>% 
  group_by(day, StatusName) %>%
  count()


d_g_miles <- d_g %>% 
  group_by(day) %>%
  summarize(miles = max(Odometer, na.rm=T) - min(Odometer, na.rm=T))

hist(d_g_miles$miles,
     xlab = "Miles",
     main = "Miles = max(Odometer) - min(Odometer)" ,
     breaks = 25, 
     col = "grey80")


d_g_miles <- d_g %>% 
  group_by(day) %>%
  summarize(miles = max(DistanceInMiles, na.rm=T))

hist(d_g_miles$miles,
     xlab = "Miles",
     main = "Miles = max(DistanceInMiles)" ,
     breaks = 25, 
     col = "grey80")

d_g_miles <- d_g %>% 
  group_by(day) %>%
  summarize(miles = max(DistanceInMiles, na.rm=T) - min(DistanceInMiles, na.rm=T))

ggplot(d_g_miles) +
  geom_histogram(aes(x = miles), bins = 50, col = "grey") +
  ggtitle("Miles = max(DistanceInMiles) - min(DistanceInMiles)") +
  xlab("Miles") +
  ylab("Frequency")

ggsave("../Figures/Frequency_miles_per_day_Distance_15301.jpg", device = "jpeg")

d_g_miles <- d_g %>% 
  group_by(day) %>%
  summarize(miles = max(Odometer, na.rm=T) - min(Odometer, na.rm=T))

ggplot(d_g_miles) +
  geom_histogram(aes(x = miles), bins = 50, col = "grey") +
  ggtitle("Miles = max(Odometer) - min(Odometer)") +
  xlab("Miles") +
  ylab("Frequency")

ggsave("../Figures/Frequency_miles_per_day_Odometer_15301.jpg", device = "jpeg")

count_miles <- left_join(d_g_count, d_g_miles, by = "day")

usewarnings = c('PDZ-R', 'PDZ-LR', 'ME - Pedestrian In Range Warning', 'PCW-LR', 'PCW-RR', 'ME - Pedestrian Collision Warning', 'PDZ - Left Front', 'PCW-LF')

count_miles <- count_miles %>%
  mutate(per_mile = n / miles) %>%
  filter(StatusName %in% usewarnings)

ggplot(count_miles %>% filter(miles > 10) ) +
  geom_line(aes(x = day, y = per_mile)) + 
  facet_wrap(~StatusName) +
  ggtitle("Events per mile (minimum 10 miles), by day")

ggsave("../Figures/Events_per_mile_15301.jpg", device = "jpeg")

ggplot(count_miles %>% filter(miles > 10)) +
  geom_histogram(aes(x = n), color = "grey", bins = 50) + 
  facet_wrap(~StatusName) + 
  ggtitle("Frequency of events per day (minimum 10 miles), by Status Name")

ggsave("../Figures/Distributions_events_15301.jpg", device = "jpeg")

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
  ggtitle("Events per mile, by week (mimimum 100 miles)")

ggsave("../Figures/Events_per_mile_by_week_15301.jpg", device = "jpeg")

ggplot(count_miles %>% filter(week_miles > 100)) +
  geom_histogram(aes(x = n), color = "grey", bins = 50) + 
  facet_wrap(~StatusName) + 
  ggtitle("Frequency of events per week (minimum 100 miles), by Status Name")

ggsave("../Figures/Distributions_events_by_week_15301.jpg", device = "jpeg")

# Time series analysis

# using day of week version

# Ituran weekly message reports

# Setup ----

library(tidyverse)
library(readxl)
library(lubridate)

setwd("//vntscex.local/DFS/3BC-Share$_Mobileye_Data/Data")

d <- read_excel("LADOT Telematics Data/MessageReport_Dec032018 weekly data.xlsx")

class(d) <- "data.frame"
names(d) <- make.names(names(d))

makenum <- c("Distance.In.Miles", "Odometer","Speed","Latitude","Longitude")
for(i in makenum) {d[,i] <- as.numeric(d[,i])}

# Date time format
dlt <- as.POSIXct(strptime(d$Loc.Time, "%m/%d/%Y %H:%M:%S"), tz = "America/Los_Angeles")
# Check it
data.frame(d$Loc.Time, dlt)[sample(1:length(dlt), 15),]
# Replace with correct format
d$Loc.Time = dlt
d$day = as.numeric(format(d$Loc.Time, "%j"))
d$week = isoweek(d$Loc.Time)
d$month = as.numeric(format(d$Loc.Time, "%m"))
d$hour = as.numeric(format(d$Loc.Time, "%H"))

# Process route name
rte <- gsub("\\\r+", "", d$POI.Recalc)
rte <- gsub("\\\n+", "", rte)

# Just get first route
rte <- substr(d$POI.Recalc, start = 1, stop = 6)
sort(table(as.factor(rte)), dec=T)
actual.dash = grep("^DASH ", rte)
# Fill NA for any values which are not actual DASH routes
rte[!1:length(rte) %in% actual.dash] = NA
sort(table(as.factor(rte)), dec=T)



d$route = rte

as.data.frame(sort(table(d$Vehicle.Name), dec=T))
hist(table(d$Vehicle.Name), col = "lightgrey", main = "Distribution of warnings by bus name")


# How many don't have info?
d %>%
  summarize(noRoute = sum(is.na(route)),
            total = n(),
            pctNoRoute = 100*noRoute/total)

# Filter for values with route info
d <- d %>% filter(!is.na(route))


# Time series ----

# Plot events by raw, and smoothed by week

d_count <- d %>% 
  group_by(Vehicle.Name, day, route, Status.Name) %>%
  count()

d_miles <- d %>% 
  group_by(Vehicle.Name, route, day) %>%
  summarize(miles = max(Distance.In.Miles))

ggplot(d_miles) +
  geom_histogram(aes(x = miles), bins = 50, col = "grey") +
  ggtitle("Miles = max(Distance in Miles by day)") +
  xlab("Miles") +
  ylab("Frequency")

ggsave("../Figures/Miles_per_day_distance_weekly_Dec.jpg", device = "jpeg")

ggplot(d_miles) +
  geom_histogram(aes(x = miles), bins = 50, col = "grey") +
  ggtitle("Miles = max(Distance in Miles by day)") +
  xlab("Miles") +
  ylab("Frequency") +
  facet_wrap(~route)

ggsave("../Figures/Miles_per_day_distance_weekly_Dec_by_route.jpg", device = "jpeg")

count_miles <- full_join(d_count, d_miles)

# usewarnings = c('PDZ-R', 'PDZ-LR', 'ME - Pedestrian In Range Warning', 'PCW-LR', 'PCW-RR', 'ME - Pedestrian Collision Warning', 'PDZ - Left Front', 'PCW-LF')

usewarnings = c("Safety - Braking - Aggressive", "Safety - Braking - Dangerous")

count_miles <- count_miles %>%
  filter(miles > 10) %>%
  mutate(per_mile = n / miles) %>%
  filter(Status.Name %in% usewarnings)

mean_per_mile <- count_miles %>%
  group_by(route, Status.Name) %>%
  summarize(mean_per_mile = mean(per_mile))

ggplot(mean_per_mile , aes(route)) +
  geom_bar(aes(weight = mean_per_mile)) + 
  ylab("Braking events per mile") +
  facet_wrap(~Status.Name) +
  ggtitle("By Route: Braking events per mile (min 10 mi driven by vehicle/day)")

ggsave("../Figures/Braking_per_mile_Dec_by_route.jpg", device = "jpeg")

mean_per_mile <- count_miles %>%
  group_by(Vehicle.Name, Status.Name) %>%
  summarize(mean_per_mile = mean(per_mile))

ggplot(mean_per_mile %>% filter(mean_per_mile > 0.01) , aes(Vehicle.Name)) +
  geom_bar(aes(weight = mean_per_mile)) + 
  ylab("Braking events per mile") +
  ggtitle("By Vehicle: Braking events per mile (>10 mi driven, > 0.1 event/mi)") +
  theme(axis.text.x = element_text(angle = 90, hjust = 1))

ggsave("../Figures/Braking_per_mile_Dec_by_vehicle.jpg", device = "jpeg")

save(list = c('d', 'count_miles'),
     file = "LADOT Telematics Data/2018-12_W1.RData")

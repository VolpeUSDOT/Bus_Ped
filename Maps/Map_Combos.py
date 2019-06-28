# -*- coding: utf-8 -*-
"""
Created on Fri Jun 28 13:24:32 2019

@author: Janice.Shiu
"""

import Layer_Mapper
import pandas as pd
import arcpy
import os

#Lists for reference
datatypes = ["All", "Braking", "PCW","PDZ"]
routes = ["A", "B", "D","E", "F"]
northsouth = ["N","S"]
months = ["Jan", "Feb", "Mar", "Apr","May","Jun","Jul",
          "Aug", "Sep", "Oct", "Nov", "Dec", "Ras"]
raster = [True, False]
cluster = [True, False]
normalization = [True, False]

def make_params(dtypes, rtes, NorSo, mon, rast, cluste, normal):
    '''
    Formats the parameters needed to make maps. Makes stacked layers using iteration.
    
    Each parameter is a list of values from the lists above.
    Method iterates through each list to make all possible combinations of parameters
    to place on a single map.
    '''
    return[(d, r, NoS, m, ras, clust, norm) for d in dtypes \
           for r in rtes \
           for NoS in NorSo \
           for m in mon \
           for ras in rast \
           for clust in cluste\
           for norm in normal]


def map_iterator(dtypes_t, dtypes, rtes_t, rtes, NorSo_t, NorSo,
                 mon_t, mon, rast_t, rast, cluste_t, cluste, normal_t, normal, makemxd = False):
    '''
    Makes combinations of unique maps. Exports table of map titles with combination values
    
    For _t parameters, use "iter" if you want unique maps of the parameter,
                            "stat" if you want the parameter stacked on one map.
                            
    For non _t parameters, use nested lists of the variables you want to iterate or stack.
    Inner nested lists are stacked.
    
    '''
    #Format variables that will be stacked on the same map
    if dtypes_t == "stat":
        dtypes = [dtypes]
    if rtes_t == "stat":
        rtes = [rtes]
    if NorSo_t == "stat":
        NorSo = [NorSo]
    if mon_t == "stat":
        mon = [mon]
    if rast_t == "stat":
        rast = [rast]
    if cluste_t == "stat":
        cluste = [cluste]
    if normal_t == "stat":
        normal = [normal]
        
    map_params = [make_params(d, r, NoS, m, ras, clust, norm) for d in dtypes \
           for r in rtes \
           for NoS in NorSo \
           for m in mon \
           for ras in rast \
           for clust in cluste\
           for norm in normal]

    #Keep track of map number
    title_num = 0
    
    #Dictionary to record the combination number
    combo_table = {
            "Map_num":[],
            "Route":[],
            "Month":[],
            "Direction":[],
            "Warning_type":[],
            "Normalization":[],
            "Raster_layer_plotted":[],
            "Cluster_layer_plotted":[],
#            "Cluster_layer_exists":[]
            }
    space = " "
    mappath = "\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\ArcMap\By_Route_All_Months_Maps"
    
    #Make every combination of map
    
    for param in map_params:
#        #Make map
#        cluster_exists, mxd = Layer_Mapper.make_map(param, space.join(["DASH","Map",str(title_num)]))
#       
#        #Save map as a .mxd if desired
#        if makemxd:
#            mxd.save(os.path.join(mappath, "DASH_Map"+"_"+str(title_num)+".mxd"))
        
        #Add information about parameters and map number to combo table
        combo_table["Map_num"].append(title_num)
        combo_table["Route"].append(param[0][1])
        combo_table["Month"].append(param[0][3])
        combo_table["Direction"].append(param[0][2])
        combo_table["Warning_type"].append(param[0][0])
        combo_table["Normalization"].append(param[0][6])
        combo_table["Raster_layer_plotted"].append(param[0][4])
        combo_table["Cluster_layer_plotted"].append(param[0][5])
#        combo_table["Cluster_layer_exists"].append(cluster_exists)
        
        title_num += 1
        print(str(title_num) + "/" + str(len(map_params)) + " Completed")
    
    #Convert dictionary to a csv
    combo_frame = pd.DataFrame(combo_table)
    combo_frame.to_csv("By_Route_All_Months.csv")
#    print(os.path.join(mappath, "By_Route_All_Months.csv"))
#    combo_frame.to_csv(os.path.join(mappath, "By_Route_All_Months.csv"))


map_iterator("iter", [["All"],["Braking"], ["PCW"],["PDZ"]], "iter", [["A"], ["B"], ["D"], ["E"], ["F"]], "stat", ["N","S"],
                 "stat", list(reversed(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Ras"])),
                 "iter", [[True],[False]], "stat", [True], "iter", [[True],[False]]) #ras, clust, norm
#No raster layer
#map_iterator("iter", datatypes, "iter", routes, "stat", northsouth,
#                 mon_t, months, "stat", [False], "stat", [True], "iter", normalization)
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 14:46:53 2019

@author: Janice.Shiu
"""

import arcpy
import os
import shutil

months = ["Jan", "Feb", "Mar", "Apr","May","Jun","Jul",
          "Aug", "Sep", "Oct", "Nov", "Dec", "Ras", "Hot"]
normalization = ["Normalized", "Unnormalized"]
datatypes = ["All", "Braking", "PCW","PDZ"]
routes = ["A", "B", "D", "E", "F"]

arcmappath = r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\ArcMap'
datapath = r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data'

rasternest=["/"+m +"/"+n+"/"+d+"/"+r+"/" for m in months for d in datatypes for r in routes for n in normalization]
clusternest=["/"+m +"/"+d+"/"+r+"/" for m in months for d in datatypes for r in routes]

if "Raster_Sorted_Layers" in os.listdir(arcmappath):
    shutil.rmtree(arcmappath + "/Raster_Sorted_Layers")
#    if "Cluster_Sorted_Layers" in os.listdir(arcmappath):
#        shutil.rmtree(arcmappath + "/Cluster_Sorted_Layers")
    
std_raster = arcpy.mapping.Layer(arcmappath + '\Standard Layers\Standard_Raster.lyr')
std_cluster = arcpy.mapping.Layer(arcmappath + '\Standard Layers\Standard_Cluster.lyr')    
for ra in rasternest:
    os.makedirs(arcmappath+"/Raster_Sorted_Layers/"+ra)
for ra in rasternest:
    for f in os.listdir(datapath+"/Raster_Sorted"+ra):
        print(f)
        if f.endswith(".tif"):
            newlyr = arcpy.mapping.Layer(datapath+"/Raster_Sorted" + ra+f)
            newlyr.saveACopy(arcmappath+"/Raster_Sorted_Layers"+ra+f)
#        std_raster.replaceDataSource(datapath+"/Raster_Sorted" +ra, "NONE",f)
#        std_raster.name = f
#        std_raster.saveACopy(arcmappath +"/Raster_Sorted"+ra+f)

#    for cl in clusternest:
#        os.makedirs(arcmappath+"/Cluster_Sorted_Layers"+cl)
#        for f in os.listdir(datapath+cl):
#            std_cluster.replaceDataSource(datapath+"/Cluster_Sorted" +cl, "NONE",f)
#            std_cluster.name = f
#            std_cluster.saveACopy(arcmappath +"/Cluster_Sorted"+cl+f)

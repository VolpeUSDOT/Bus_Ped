# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 14:46:53 2019

@author: Janice.Shiu
"""

import arcpy
import os
import shutil
import glob

#Folder names for the nested directories
months = ["Jan", "Feb", "Mar", "Apr","May","Jun","Jul",
          "Aug", "Sep", "Oct", "Nov", "Dec", "Ras", "Hot"]
normalization = ["Normalized", "Unnormalized"]
datatypes = ["All", "Braking", "PCW","PDZ"]
routes = ["A", "B", "D", "E", "F"]

#Working paths for source(datapath) destination (arcmappath)
datapath = r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data'
arcmappath = r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\ArcMap'

#Create directories for nested paths
rasternest=[os.path.join(m,n,d,r) for m in months for d in datatypes for r in routes for n in normalization]
clusternest=[os.path.join(m, d, r) for m in months for d in datatypes for r in routes]

#Remove any old folders created
'''
print("Removing Folders")
if "Raster_Sorted_Layers" in os.listdir(arcmappath):
    shutil.rmtree(os.path.join(arcmappath, "Raster_Sorted_Layers"))
if "Cluster_Sorted_Layers" in os.listdir(arcmappath):
    shutil.rmtree(os.path.join(arcmappath,"Cluster_Sorted_Layers"))
'''

#Make directories for raster layers
#Turn .tif raster files into arcmap layers
print("Making Raster Layers")
for ra in rasternest:
    os.makedirs(os.path.join(arcmappath,"Raster_Sorted_Layers",ra))
for ra in rasternest:
    for f in os.listdir(os.path.join(datapath,"Raster_Sorted",ra)):
        if f.endswith(".tif"):
            newlyr = arcpy.mapping.Layer(os.path.join(datapath,"Raster_Sorted",ra,f))
            newlyr.saveACopy(os.path.join(arcmappath,"Raster_Sorted_Layers",ra,f))

#Make directories for cluster layers
#Turn .shp cluster files into arcmap layers
print("Making Cluster Layers")
for cl in clusternest:
    os.makedirs(os.path.join(arcmappath, "Cluster_Sorted_Layers", cl))
for cl in clusternest:
    for f in glob.glob(os.path.join(datapath, "Cluster_Sorted", cl, "*.shp")):
        newlyr =  arcpy.mapping.Layer(f)
        newlyr.saveACopy(os.path.join(arcmappath,"Cluster_Sorted_Layers",cl, os.path.basename(f)))
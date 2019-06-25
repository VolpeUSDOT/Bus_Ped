# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 14:46:53 2019

@author: Janice.Shiu
"""

import arcpy
print("running")
#Start with a map document
mxd = arcpy.mapping.MapDocument("CURRENT")
mxd.author = "Volpe"

#Add Route. Will always be at the top of the layers list 
routeb = arcpy.mapping.Layer(r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data\Routes\Route_Layers\Route_B.lyr')
df = arcpy.mapping.ListDataFrames(mxd, "Layers")[0]
arcpy.mapping.AddLayer(df,routeb)

print("Add basemap")
#Add Basemap. Will always be at the bottom of the layers list
basemapLayer = arcpy.mapping.Layer(r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\ArcMap\Basemap.lyr')   
df = arcpy.mapping.ListDataFrames(mxd, "*")[0]
arcpy.mapping.AddLayer(df, basemapLayer, "BOTTOM")

print("Add Raster")
#Add layer of raster data
rastlyr = arcpy.mapping.Layer(r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\ArcMap\Raster_Unnormalized_All_DASHtest.lyr')
df = arcpy.mapping.ListDataFrames(mxd, "*")[0]
'''
#Get metadata to set the name and to find whether the is a matching dataset in
#the cluster data
file_decomp = file.split("_")
mon = file_decomp[0][0:3]
if mon == "Ras":
    
dtype = datatypes[lc_datatype.index(file_decomp[2].lower())]
shutil.copy(src = path+"/Cluster/"+ file, dst = path+"/Cluster_Sorted/"+mon+"/"+dtype)
'''
rastlyr.name = "TEMP"
arcpy.mapping.AddLayer(df,rastlyr)

print("standardize")
#Update Raster Layer to standard
updateLayer = arcpy.mapping.ListLayers(mxd, "", df)[1]
sourceLayer = arcpy.mapping.Layer(r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\ArcMap\Standard_Raster.lyr')
arcpy.mapping.UpdateLayer(df, updateLayer, sourceLayer, True)

#Add layer of cluster data

#How to make a raster layer from a file
#test = arcpy.MakeRasterLayer_management(r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data\Raster\AprilRaster_Unnormalized_Braking_DASH.A.N.tif', "test")

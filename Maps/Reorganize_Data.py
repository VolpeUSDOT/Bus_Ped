# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 13:44:17 2019

@author: Janice.Shiu
"""
import os
import shutil
path = r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data'
#Reorganize data into folders by month and normalization

#Remove any old folders
#if "Raster_Sorted" in os.listdir(path):
#    shutil.rmtree(path + "/Raster_Sorted")
if "Cluster_Sorted" in os.listdir(path):
    shutil.rmtree(path + "/Cluster_Sorted")
    
#Create filesystem
months = ["Jan", "Feb", "Mar", "Apr","May","Jun","Jul",
          "Aug", "Sep", "Oct", "Nov", "Dec", "Ras", "Hot"]
normalization = ["Normalized", "Unnormalized"]
datatypes = ["All", "Braking", "PCW","PDZ"]
routes = ["A", "B", "D", "E", "F"]

for m in months:
    for d in datatypes:
        for r in routes :
            os.makedirs(path + "/Cluster_Sorted/" + m + "/" + d + "/" + r)
            for n in normalization:
#                os.makedirs(path + "/Raster_Sorted/" + m + "/" + n + "/" + d + "/" + r)
                continue

#Have a lowercase version of datatypes so we can better identify the types
#Because the name of the datatype is inconsistent across files
datatypes = ["All", "Braking", "PCW","PDZ"]
lc_datatype = ["all", "braking", "pcw","pdz"]
dtypes = []

'''
##Sort Raster Data
for file in os.listdir(path + "\Raster"):
    file_decomp = file.split("_")
    mon = file_decomp[0][0:3]
    try:
        norm = file_decomp[1]
    except:
        break
    dtype = datatypes[lc_datatype.index(file_decomp[2].lower())]
    try:
        route = routes[routes.index(file_decomp[3].split(".")[-3])]
    except:
        print(file)
    shutil.copy(src = path+"/Raster/"+file,
                    dst = path+"/Raster_Sorted/"+mon+"/"+norm+"/"+dtype+ "/" + route)
'''
#Sort Cluster Data
for file in os.listdir(path + "\Cluster"):
    try:
        if not file.endswith(".txt") and file != "Archive" and \
        not file.endswith(".lock"):
            file_decomp = file.split("_")
            mon = file_decomp[0][0:3]
            dtype = datatypes[lc_datatype.index(file_decomp[2].lower())]
            route = routes[routes.index(file_decomp[3].split(".")[-3])]
            shutil.copy(src = path+"/Cluster/"+ file, dst = path+"/Cluster_Sorted/"+mon+"/"+dtype+"/" + route)
    except:
        print(file)
        break
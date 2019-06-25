# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 13:44:17 2019

@author: Janice.Shiu
"""
import os
import shutil

#Reorganize data into folders by month and normalization
path = "\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data"

#Remove any old folders
#if "Raster_Sorted" in os.listdir():
#    shutil.rmtree(path + "/Raster_Sorted")
if "Cluster_Sorted" in os.listdir():
    shutil.rmtree(path + "/Cluster_Sorted")
    
#Create filesystem
months = ["Jan", "Feb", "Mar", "Apr","May","Jun","Jul",
          "Aug", "Sep", "Oct", "Nov", "Dec", "Ras", "Hot"]
normalization = ["Normalized", "Unnormalized"]
datatypes = ["All", "Braking", "PCW","PDZ"]

for m in months:
    for d in datatypes:
        os.makedirs(path + "/Cluster_Sorted/" + m + "/" + d)
        for n in normalization:
#            os.makedirs(path + "/Raster_Sorted/" + m + "/" + n + "/" + d)
            continue

#Have a lowercase version of datatypes so we can better identify the types
#Because the name of the datatype is inconsistent across files
datatypes = ["All", "Braking", "PCW","PDZ"]
lc_datatype = ["all", "braking", "pcw","pdz"]
dtypes = []


##Sort Raster Data
#for file in os.listdir(path + "\Raster"):
#    file_decomp = file.split("_")
#    mon = file_decomp[0][0:3]
#    norm = file_decomp[1]
#    dtype = datatypes[lc_datatype.index(file_decomp[2].lower())]
#    shutil.copy(src = path+"/Raster/"+file,
#                    dst = path+"/Raster_Sorted/"+mon+"/"+norm+"/"+dtype)


#Sort Cluster Data
for file in os.listdir(path + "\Cluster"):
    try:
        if not file.endswith(".txt") and file != "Archive" and \
        not file.endswith(".lock"):
            file_decomp = file.split("_")
            mon = file_decomp[0][0:3]
            dtype = datatypes[lc_datatype.index(file_decomp[2].lower())]
            shutil.copy(src = path+"/Cluster/"+ file, dst = path+"/Cluster_Sorted/"+mon+"/"+dtype)
    except:
        print(file)
        break
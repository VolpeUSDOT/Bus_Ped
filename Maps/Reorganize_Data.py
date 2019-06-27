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

print("Removing Folders")
if "Raster_Sorted" in os.listdir(path):
    shutil.rmtree(os.path.join(path,"Raster_Sorted"))
if "Cluster_Sorted" in os.listdir(path):
    shutil.rmtree(os.path.join(path,"Cluster_Sorted"))

#Create filesystem
print("Creating Filesystem")
months = ["Jan", "Feb", "Mar", "Apr","May","Jun","Jul",
          "Aug", "Sep", "Oct", "Nov", "Dec", "Ras", "Hot"]
normalization = ["Normalized", "Unnormalized"]
datatypes = ["All", "Braking", "PCW","PDZ"]
routes = ["A", "B", "D", "E", "F"]

for m in months:
    for d in datatypes:
        for r in routes :
            os.makedirs(os.path.join(path,"Cluster_Sorted",m,d,r))
            for n in normalization:
                os.makedirs(os.path.join(path, "Raster_Sorted",m,n,d,r))

#Have a lowercase version of datatypes so we can better identify the types
#Because the name of the datatype is inconsistent across files
datatypes = ["All", "Braking", "PCW","PDZ"]
lc_datatype = ["all", "braking", "pcw","pdz"]
dtypes = []


#Sort Raster Data
print("Sorting Raster Data")
for file in os.listdir(os.path.join(path,"Raster")):
    filename, fileext = os.path.splitext(file)
    if fileext == ".tif":
        #Remove periods from the name
        filename = filename.replace(".", "_") + fileext
        
        #Decompose where the file belongs
        file_decomp = filename.split("_")
        mon = file_decomp[0][0:3]
        norm = file_decomp[1]
        dtype = datatypes[lc_datatype.index(file_decomp[2].lower())]
        route = file_decomp[4]
        
        #Copy the file into the sorted directory with the corrected name
        shutil.copy(src = os.path.join(path,"Raster", file),
                    dst = os.path.join(path, "Raster_Sorted", mon, norm, dtype, route, filename))

#Sort Cluster Data
print("Sorting Cluster Data")
for file in os.listdir(path + "\Cluster"):
    filename, fileext = os.path.splitext(file)
    if fileext == ".shp" or fileext == ".dbf" or fileext == ".prj" or fileext == ".shx":
        #Remove periods from the name
        filename = filename.replace(".","_") + fileext
        
        #Decompose where the file belongs
        file_decomp = filename.split("_")
        mon = file_decomp[0][0:3]
        dtype = datatypes[lc_datatype.index(file_decomp[2].lower())]
        route = file_decomp[4]
        
        shutil.copy(src = os.path.join(path, "Cluster", file),
                    dst = os.path.join(path, "Cluster_Sorted", mon, dtype, route, filename))
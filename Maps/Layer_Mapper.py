# -*- coding: utf-8 -*-
"""
Created on Tue Jun 25 17:22:06 2019

@author: Janice.Shiu
"""
import arcpy 
import os

arcmappath =r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\ArcMap'

months = ["Jan", "Feb", "Mar", "Apr","May","Jun","Jul",
          "Aug", "Sep", "Oct", "Nov", "Dec", "Ras", "Hot"]
normalization = ["Normalized", "Unnormalized"]
datatypes = ["All", "Braking", "PCW","PDZ"]
routes = ["A", "B", "D", "E", "F"]

#Start with a map document
mxd = arcpy.mapping.MapDocument(arcmappath + '/StandardMap.mxd')
mxd.author = "Volpe"
params = [("Braking","A","S","Aug",True,False,False)]
for p in params:
    #p = (str interaction type, str route letter, str N or S, str month, bool plot raster, bool plot clust, bool normalized)
    d, r, NoS, m, ras, clust, norm = p
    
    
    #Add Route. Will always be at the top of the layers list 
    print(arcmappath + '\Standard Layers\Route_'+ r +'.lyr')
    route = arcpy.mapping.Layer(arcmappath + '/Standard Layers/Route_'+ r +'.lyr')
    df = arcpy.mapping.ListDataFrames(mxd, "Layers")[0]
    print("Adding route")
    arcpy.mapping.AddLayer(df,route)
    '''
    #Set Scale
    for df in arcpy.mapping.ListDataFrames(mxd):
        df.scale = 24000
    '''
    
    #Add layer of raster data
    if ras == True:
        print("Adding Raster")
        try:
            n = "Normalized" if norm == True else "Unnormalized"
            filepath =arcmappath + '/Raster_Sorted_Layers/'+"/"+m +"/"+n+"/"+d+"/"+r
            
            #Find the right file to map and map it
            for f in os.listdir(filepath):
                if f.split(".")[-2] == NoS:
                    #Create layer
                    rastlyr = arcpy.mapping.Layer(filepath+"/" + f)
                    
                    #Format layer name
                    space = " "
                    rastlyr.name = space.join([n, d, "DASH", r, "-", NoS, m])
                    
                    #Map layer
                    arcpy.mapping.AddLayer(df,rastlyr)

                    #Update layer to standard symbology
                    updateLayer = arcpy.mapping.ListLayers(mxd, "", df)[1]
                    sourceLayer = arcpy.mapping.Layer(arcmappath + 
                                                      '/Standard Layers/Standard_'+n+'_Raster.lyr')
                    arcpy.mapping.UpdateLayer(df, updateLayer, sourceLayer, True)                        
        except:
            #Print errors if raster file does not exist
            comma = ", "
            print("Raster file for "+ comma.join(["Datatype " + d,
                                                  "Route " + r + NoS, m]) + "does not exist.")
            answer = input("Proceed without layer? Y or N: ")
            if answer == "N":
                print("Layer_Mapper.py Terminated")
                break
    #Add cluster layer
    if clust == True:
        print("Cluster layers not available yet. Proceeding without plotting clusters.")
        '''
        try:
            n = "Normalized" if norm == True else "Unnormalized"
            filepath =arcmappath + '/Cluster_Sorted_Layers/'+"/"+m +"/"+d+"/"+r
            
            #Find the right file to map and map it
            for f in os.listdir(filepath):
                if f.split(".")[-2] == NoS:
                    #Create layer
                    clustlyr = arcpy.mapping.Layer(filepath+"/" + f)
                    
                    #Format layer name
                    space = " "
                    clustlyr.name = space.join(["HOTSPOT", d, "DASH", r, "-", NoS, m])
                    
                    #Map layer
                    arcpy.mapping.AddLayer(df,clustlyr)

                    #Update layer to standard symbology
                    updateLayer = arcpy.mapping.ListLayers(mxd, "", df)[1]
                    sourceLayer = arcpy.mapping.Layer(arcmappath + 
                                                      '\Standard Layers\Standard_Cluster.lyr')
                    arcpy.mapping.UpdateLayer(df, updateLayer, sourceLayer, True)                        
        except:
            #Print errors if cluster file does not exist, but keep going
            comma = ", "
            print("Cluster file for "+ comma.join(["Datatype " + d,
                                                  "Route " + r + NoS, m]) + "does not exist.")
            print("Proceeding without layer.")
        '''
#######################################################################################################################################                
#Add Basemap. Will always be at the bottom of the layers list
basemapLayer = arcpy.mapping.Layer(arcmappath + '\Standard Layers\Basemap.lyr')
arcpy.mapping.AddLayer(df, basemapLayer, "BOTTOM")

#Insert Legend
legend = arcpy.mapping.ListLayoutElements(mxd, "LEGEND_ELEMENT", "Legend")[0]
legend.autoAdd = True

#Save as pdf
arcpy.mapping.ExportToPDF(mxd, r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\ArcMap\MapPDFs\test.pdf')
    
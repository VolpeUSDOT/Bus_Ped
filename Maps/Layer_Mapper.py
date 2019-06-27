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
mxd = arcpy.mapping.MapDocument(os.path.join(arcmappath,'StandardMap.mxd'))
mxd.author = "Volpe"
#params = [("PCW","A","S","Apr",True,True,False)]
params = [("PCW","A","S","Apr",True,True,False),("PCW","A","N","Apr",True,True,False),("Braking","F","S","Aug",True,True,False)]
# params = [("Braking","F","S","Aug",True,False,False),("Braking","B","N","Aug",True,False,False)]
#          ("Braking","D","S","Aug",True,False,False),("Braking","E","S","Aug",True,False,False),
#          ("Braking","F","S","Aug",True,False,False)]

#Keep track of what routes and clusters have been added to keep track of layer order
routes_mapped = []
num_clust = 0
for p in params:
    ###
#    d : interaction type. See datatypes list for the available types.
#    r: route letter. See routes list for available routes.
#    NoS: "N" or "S" route
#    m : 3 letter month code. See months list for available months and alternative types.
#    ras = True or False, whether to plot rasters
#    clust = True or False, whether to plot clusters
#    norm = True or False, whether to plot normalized data
    ###
    d, r, NoS, m, ras, clust, norm = p
    
    #Add route to the map if it hasn't been added yet
    if r not in routes_mapped:
        route = arcpy.mapping.Layer(os.path.join(arcmappath,'Standard Layers','Route_'+r+'.lyr'))
        df = arcpy.mapping.ListDataFrames(mxd, "Layers")[0]
        arcpy.mapping.AddLayer(df,route)
        routes_mapped.append(r)
        
    '''
    #Set Scale
    for df in arcpy.mapping.ListDataFrames(mxd):
        df.scale = 24000
    '''
    
    #Add layer of raster data
    if ras == True:
        n = "Normalized" if norm == True else "Unnormalized"
        filepath =os.path.join(arcmappath, "Raster_Sorted_Layers",m,n,d,r)
        
        #Find the right file to map and map it
        #Keep count of how many new routes are added and whether raster has been added
        ras_updated = False
        for f in os.listdir(filepath):
            if os.path.splitext(f)[0][-1] == NoS:
                try:
                    n = "Normalized" if norm == True else "Unnormalized"
                    filepath =os.path.join(arcmappath, "Raster_Sorted_Layers",m,n,d,r)
                    
                    #Find the right file to map and map it
                    #Keep count of how many new routes are added
                    
                    for f in os.listdir(filepath):
                        if os.path.splitext(f)[0][-1] == NoS:
                            #Create layer OF RASTER DATA
                            rastlyr = arcpy.mapping.Layer(os.path.join(filepath, f))
                            
                            #Format layer name
                            space = " "
                            rastlyr.name = space.join([n, d, "DASH", r, "-", NoS, m])
                            
                            #Map layer
                            arcpy.mapping.AddLayer(df,rastlyr)
                            
                            #Update layer to standard symbology
                            updateLayer = arcpy.mapping.ListLayers(mxd, "", df)[len(routes_mapped)+num_clust]
                            sourceLayer = arcpy.mapping.Layer(os.path.join(arcmappath, 
                                                              'Standard Layers','Standard_'+n+'_Raster.lyr'))
                            arcpy.mapping.UpdateLayer(df, updateLayer, sourceLayer, True)
                            ras_updated = True
                except:
                    ras_updated = False
        if ras_updated == False:
            #Print errors if raster file does not exist, and therefore the layer wasn't added
            n = "Normalized" if norm == True else "Unnormalized"
            comma = ", "
            print("Raster file for "+ comma.join(["Datatype " + d,"Route " + r + "-"+ NoS, m,
                                                  n]) + " does not exist.")
        
    #Add cluster layer
    if clust == True:
        n = "Normalized" if norm == True else "Unnormalized"
        filepath = os.path.join(arcmappath, "Cluster_Sorted_Layers", m,d,r)
        
        #Find the right file to map and map it
        clust_updated = False #variable to keep track of whether cluster was added
        for f in os.listdir(filepath):
            if os.path.splitext(f)[0][-1] == NoS:
                try:
                    n = "Normalized" if norm == True else "Unnormalized"
                    filepath = os.path.join(arcmappath, "Cluster_Sorted_Layers", m,d,r)
                    
                    #Find the right file to map and map it
                    for f in os.listdir(filepath):
                        if os.path.splitext(f)[0][-1] == NoS:
                            #Create layer
                            clustlyr = arcpy.mapping.Layer(os.path.join(filepath,f))
                            
                            #Format layer name
                            space = " "
                            clustlyr.name = space.join(["HOTSPOT", d, "DASH", r, "-", NoS, m])
                            
                            #Map layer
                            arcpy.mapping.AddLayer(df,clustlyr)
            
                            #Update layer to standard symbology
                            updateLayer = arcpy.mapping.ListLayers(mxd, "", df)[len(routes_mapped)]
                            sourceLayer = arcpy.mapping.Layer(os.path.join(arcmappath, "Standard Layers", "Standard_Cluster.lyr"))
                            arcpy.mapping.UpdateLayer(df, updateLayer, sourceLayer, True)
                            num_clust +=1
                            clust_updated = True
                except:
                    clust_updated = False
                    
        if clust_updated == False:
            #print errors if cluster file does not exist, and therefore the layer wasn't added
            comma = ", "
            print("Cluster file for "+ comma.join(["Datatype" + d,
                                                  "Route " + r +"-"+ NoS, m]) + " does not exist.")
            print("Proceeding without layer.")

#######################################################################################################################################                
#Add Basemap. Will always be at the bottom of the layers list
basemapLayer = arcpy.mapping.Layer(os.path.join(arcmappath,'Standard Layers','Basemap.lyr'))
arcpy.mapping.AddLayer(df, basemapLayer, "BOTTOM")

#Insert Legend
legend = arcpy.mapping.ListLayoutElements(mxd, "LEGEND_ELEMENT", "Legend")[0]
legend.autoAdd = True

#Save as pdf
underscore = "_"
mappath = r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\ArcMap\MapPDFs'
arcpy.mapping.ExportToPDF(mxd, "test.pdf")
#arcpy.mapping.ExportToPDF(mxd, os.path.join(mappath, underscore.join([n,d,"DASH",r,NoS,m])+".pdf"))    
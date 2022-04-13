# Using virtual environment cloned from ArcGIS Pro
import arcpy
import time
import os

class CostPathFromSurface:
    '''This is a class created to contain the methods needed to convert a vector hex suitability
    surface into a Least Cost Path vector Line.  The primary inputs are names of the vector surface,
    origin point, and destination point, and the primary output is the Least Cost Path vector route.
    First instanstiate a new CostPathFromSurface Object, then execute the .runGeoTool() method.
    
    To activate python virtual environment with arcpy:
    Install and open ArcGIS Pro (Airspace Link has ArcGIS Pro Licenses)
    => Settings => Python => Manage Environments => Clone Default (arcgispro-py3)
    The default arcgispro-py3 env is here: C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3>
    It is reccomended to clone the default environment to avoid corrupting it.
    
    :param workSpaceGDB: path to File GeoDatabase with input data
    :type workSpaceGDB: str
    :param surfaceFile: vector suitability hex surface name, no file ext needed
    :type surfaceFile: str
    :param originLoc: route origin Point Feature Class 
    :type originLoc: str
    :param destLoc: route destination Point Feature Class
    :type destLoc: str
    :param siteName: used for file naming outputs, no spaces
    :type siteName: str
    :param inPrj: input route points Feature Class projection (raster expected to be unprojected)
    :type inPrj: str
    :param outPrj: output projection
    :type outPrj: str
    :param surfaceAttr: vector surface attribute to be used in generating raster surface
    :type surfaceAttr: str
    :param rastCellSize: raster surface output cellsize
    :type rastCellSize: str
    :param simpTol: line simplification tolerance e.g. '300 Meters'
    :type simpTol: str

    Example workflow:
    # Input Parameters
    workSpaceGDB = 'C:\\Users\\Eric Kerney\\arcgisNotebooks\\leastCost\\Surface_v2.gdb\\Surface.gdb'
    surfaceFile, originLoc, destLoc, siteName = 'PendletonOR_SuitabilitySurface', 'TribalCenter', 'Pendleton_Lab', 'pendleOR'
    inPrj = 'GEOGCS[\"GCS_WGS_1984\",DATUM[\"D_WGS_1984\",SPHEROID[\"WGS_1984\",6378137.0,298.257223563]],PRIMEM[\"Greenwich\",0.0],UNIT[\"Degree\",0.0174532925199433]]'
    outPrj = 'PROJCS[\"US_National_Atlas_Equal_Area\",GEOGCS[\"GCS_Sphere_Clarke_1866_Authalic\",DATUM[\"D_Sphere_Clarke_1866_Authalic\",SPHEROID[\"Sphere_Clarke_1866_Authalic\",6370997.0,0.0]],PRIMEM[\"Greenwich\",0.0],UNIT[\"Degree\",0.0174532925199433]],PROJECTION[\"Lambert_Azimuthal_Equal_Area\"],PARAMETER[\"False_Easting\",0.0],PARAMETER[\"False_Northing\",0.0],PARAMETER[\"Central_Meridian\",-100.0],PARAMETER[\"Latitude_Of_Origin\",45.0],UNIT[\"Meter\",1.0]]'
    surfaceAttr, rastCellSize, simplifyTol = 'score_v2', '0.0004','300 Meters'
    # Instantite Class
    surfacePath = CostPathFromSurface(workSpaceGDB, surfaceFile, originLoc, destLoc, siteName, inPrj, outPrj, surfaceAttr, rastCellSize, simplifyTol)
    # Run Process
    surfacePath.runGeoTool()
    '''    
    
    def __init__(self, workSpaceGDB: str, surfaceFile: str, originLoc: str, destLoc: str, siteName: str,
                 inPrj: str, outPrj: str, surfaceAttr: str, rastCellSize: str, simpTol: str):
        '''Constructor method
        Assign all parameters and setup arcpy workspace and scratc environment.
        '''        
        self.workSpaceGDB,self.surfaceFile,self.originLoc,self.destLoc,self.siteName = workSpaceGDB,surfaceFile,originLoc,destLoc,siteName
        self.inPrj,self.outPrj,self.surfaceAttr,self.rastCellSize, self.simpTol = inPrj, outPrj, surfaceAttr, rastCellSize, simpTol
        self.timeSuffix, self.resamplingType, self.prjRastCellSize = time.strftime('%d%m%Y%H%M%S'), 'NEAREST', '45.6326806908288 45.6326806908286'
    
        arcpy.env.workspace, arcpy.env.overwriteOutput = self.workSpaceGDB, True
        self.scratch = arcpy.env.scratchGDB

    def runGeoTool(self):
        '''Execute all methods in workflow:
        self.surfaceVecToRast()     # Convert vector suitabilty surface into raster
        self.projectRaster()        # Project raster surface into output coordinate system
        self.projectLocations()     # Project origin and destination feature class into output coordinate system
        self.leastCostPath()        # Generate least cost path using projected inputs
        self.simplifyToGeoJSON()    # Simplify least cost path with barriers, generalize path, output to GeoJSON
        '''        
        self.surfaceVecToRast()
        self.projectRaster()
        self.projectLocations()
        self.leastCostPath()
        self.simplifyToGeoJSON()

    # Convert surface vector into raster format - self.rasterSurface
    def surfaceVecToRast(self):
        '''Convert vector suitabilty surface into raster
        :return: Prints success message with name of surface raster with and time stamp, e.g.
        Surface Vector to Raster Success: pendleOR_rasterSurface_06042022105357
        :rtype: none
        '''             
        self.rasterSurface = (f'{self.siteName}_rasterSurface_{self.timeSuffix}')
        arcpy.conversion.PolygonToRaster(self.surfaceFile, self.surfaceAttr, self.rasterSurface, cell_assignment="CELL_CENTER", 
                                         priority_field="NONE", cellsize=self.rastCellSize, build_rat="BUILD")
        print(f'Surface Vector to Raster Success: {self.rasterSurface}')

    # Project surface raster
    def projectRaster(self):
        '''Project raster surface into output coordinate system
        :return: Prints success message with name of projected surface raster and time stamp, e.g.
        Project Raster Success: pendleOR_rasterSurfaceProject_06042022105357
        :rtype: none
        '''          
        self.rastSurfProjName = (f'{self.siteName}_rasterSurfaceProject_{self.timeSuffix}')
        self.rasterSurfaceProject = arcpy.management.ProjectRaster(self.rasterSurface, self.rastSurfProjName, out_coor_system=self.outPrj, 
            resampling_type=self.resamplingType, cell_size=self.prjRastCellSize, geographic_transform=[], Registration_Point="", 
            in_coor_system="", vertical="NO_VERTICAL")
        print(f'Project Raster Success: {self.rastSurfProjName}') 
            
    # Project origin and destination vector points
    def projectLocations(self):
        '''Project origin and destination feature class into output coordinate system
        :return: Prints success message with name of projected origin/destination e.g.
        Project origin/destination Success: TribalCenter_orjProj - Pendleton_Lab_orjProj
        :rtype: none
        '''        
        self.originProj = arcpy.management.Project(self.originLoc, (f'{self.originLoc}_orjProj'), out_coor_system=self.outPrj, transform_method=[], 
            in_coor_system=self.inPrj, preserve_shape="NO_PRESERVE_SHAPE", max_deviation="", vertical="NO_VERTICAL")
        self.destProj = arcpy.management.Project(self.destLoc, (f'{self.destLoc}_orjProj'), out_coor_system=self.outPrj, transform_method=[], 
            in_coor_system=self.inPrj, preserve_shape="NO_PRESERVE_SHAPE", max_deviation="", vertical="NO_VERTICAL")
        print(f'Project origin/destination Success: {self.originLoc}_orjProj - {self.destLoc}_orjProj')
    
    # And finally generate leastCostPath!
    def leastCostPath(self):
        '''Generate least cost path with arcpy.intelligence.LeastCostPath using projected inputs
        :return: Prints success message with location and name of leastCostPath e.g.
        Simplified GeoJSON Path Finished: pendleOR_GeoJSON_06042022110700
        :rtype: none
        '''         
        with arcpy.EnvManager(scratchWorkspace=self.scratch, workspace=self.scratch):
            self.costPathOut = arcpy.intelligence.LeastCostPath(self.rasterSurfaceProject, self.originProj, self.destProj, 
            (f'{self.workSpaceGDB}\\{self.siteName}_leastCostPath'), "SMALL_POSITIVE")
            print(f'LeastCostPath Generated! - {self.workSpaceGDB}\\{self.siteName}_leastCostPath')

    def simplifyToGeoJSON(self):
        '''Simplify least cost path with barriers, generalize path, output to GeoJSON, arcpy.FeaturesToJSON_conversion
        :return: Prints success message with name of simplified GeoJSON file e.g.
        Simplified GeoJSON Path Finished: pendleOR_GeoJSON_06042022110700.geojson
        :rtype: none
        '''       
        #Create Barrier
        self.barrier, self.barCount = arcpy.management.SelectLayerByAttribute(in_layer_or_view=self.surfaceFile, 
            selection_type="NEW_SELECTION", where_clause="score_v2 > 4", invert_where_clause="")
        #Simplify Line
        simpLine = (f'{self.siteName}_simpLine_{self.timeSuffix}')
        self.simpLineOut = arcpy.cartography.SimplifyLine(in_features=self.costPathOut, out_feature_class=simpLine, algorithm="WEIGHTED_AREA", 
            tolerance=self.simpTol, error_resolving_option="RESOLVE_ERRORS", collapsed_point_option="NO_KEEP", error_checking_option="CHECK", 
            in_barriers=[self.barrier])
        #Generalize Line Further 
        self.pathGen = arcpy.edit.Generalize(in_features=self.simpLineOut, tolerance="100 Meters")
        #Output GeoJSON
        self.geoJSON = arcpy.FeaturesToJSON_conversion(in_features = self.pathGen, out_json_file=(f'{self.siteName}_GeoJSON_{self.timeSuffix}'), 
            format_json="FORMATTED", geoJSON="GEOJSON", outputToWGS84="WGS84")
        print(f'Simplified GeoJSON Path Finished: {self.siteName}_GeoJSON_{self.timeSuffix}.geojson')

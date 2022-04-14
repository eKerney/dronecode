# install dependencies and python package install function for python-dotenv
import subprocess
import sys
import os
import requests
import json
import pandas as pd
import time

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])    
install('python-dotenv')

class RouteToWaypoints:
    '''This class ingests simplified GeoJSON output from the :class: 'CostPathFromSurface' class,
    first loading the GeoJSON LineString file, then adding CARS elevation data to points via Airspace Link 
    Azure function, next calculating the altitude from the CARS attributes and AGL parameter, then generating 
    a .waypoints file from the leastCostPath in QGroundControl filw version - QGC WPL 110
    Dependencies: requests, json, pandas, subprocess, sys, os, python-dotenv
    python-dot is required to load client credentials from dotenv file in project root directory
    The tab separated attributes in waypoints export are in the following order:
    'INDEX', 'CURRENT', 'COORD_FRAME', 'COMMAND', 'PARAM1', 'PARAM2', 'PARAM3', 'PARAM4', 'PARAM5/X/LATITUDE',
    'PARAM6/Y/LONGITUDE', 'PARAM7/Z/ALTITUDE', 'AUTOCONTINUE'
    :param geoJSONpath: path to GeoJSON file
    :type geoJSONpath: str
    :param z_units: ft or m 
    :type z_units: str
    :param agl: flight altitude Above Ground Level, units specified above
    :type agl: float
    :param outName: waypoints output filename
    :type outName: str

    # Example Workflow
    inputData = 'SampleRoutes_v2.geojson'
    z_units = 'ft'
    agl = 400
    outputName = 'PendletonRoutes'
    routes = RouteToWaypoints(inputData, z_units, agl, outputName)
    routes.runGeoTool()
    ''' 
    
    def __init__(self, geoJSONpath: str, z_units: str, agl: float, outName: str,
                 featureType: str='LINESTRING', in_prj: str ='EPSG:4269', in_type: str='ellipsoid',):
        '''Constructor method
        '''
        self.inputPath, self.z_units, self.agl, self.featureType = geoJSONpath, z_units, agl, featureType
        self.in_prj, self.in_type, self.outName = in_prj, in_type, outName
        self.runGetToken()

    def runGetToken(self):   
        def get_token(client_id: str, client_key: str, scope: str, subscription_key: str) -> str:
            """
            Get an oauth token from the api
            :param client_id: Client ID
            :param client_key: Client Secret
            :param scope: Oauth Scope
            :param subscription_key: Subscription ID
            :return: Bearer Token
            :raises SystemError: System error if unable to get token
            """
            token_body = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_key,
                "scope": requests.utils.quote(scope),
            }
            header = {
                "x-api-key": subscription_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            response = requests.post(
                "https://airhub-api.airspacelink.com/v1/oauth/token",
                data=token_body,
                headers=header,
            )
            if response.status_code != 200:
                raise SystemError(
                    f"Unable to get oauth token due to: ({response.status_code}) {response.json()['message']}"
                )
            return response.json()["data"]["accessToken"]

        # install and load .env
        install('python-dotenv')
        from dotenv import load_dotenv 
        load_dotenv()
        # load env keys
        client_key = os.getenv('CLIENT_SECRET')
        client_id = os.getenv('CLIENT_ID')
        api_scope = os.getenv('API_SCOPE')
        subscription = os.getenv('SUBSCRIPTION')
        url = os.getenv('URL')
        # obtain token for CARS API request
        token = get_token(client_id, client_key, api_scope, subscription)
        self.subscription_key = subscription
        self.token = token
        print(f'Obtained token for Client ID: {client_id}')

    def runGeoTool(self):
        '''Execute all methods in workflow:
        self.loadGeoJSON()          # Loads GeoJSON file generated from :class:'CostPathFromSurface' class
        self.addCARSdata()          # Takes loaded GeoJSON and sends to Airspace Link CARS function which adds elevation attributes
        self.addAglGeoJSON()        # With geoJSONarr from CARS function, calculate flight altitude
        self.exportToWaypoints()    # Convert GeoJSON Feature Collection(s) into waypoints export as tab sep text file
        '''        
        self.loadGeoJSON()
        self.addCARSdata()
        self.addAglGeoJSON()
        return self.exportToWaypoints()

    # Load raw GeoJSON file as JSON     
    def loadGeoJSON(self):
        '''Loads GeoJSON file generated from :class:'CostPathFromSurface' class
        :return: Prints success message with name of loaded GeoJSON e.g.
        Loaded GeoJSON: pendleOR_GeoJSON_17032022144129.geojson
        :rtype: none
        '''         
        f = open(self.inputPath)
        self.loadedGeoJSON = json.load(f)
        print(f'Loaded GeoJSON: {self.inputPath}')

    # send in memory GeoJSON to CARS
    def addCARSdata(self):
        '''Takes loaded GeoJSON and sends to Airspace Link CARS function which adds elevation attributes, 
        :return: Prints success message with provided flight AGL e.g.
        CARS Data Request Success Flight AGL: 400 ft
        :rtype: none
        '''  
        self.geoJSONarr = []
        url = 'https://airhub-api.airspacelink.com/v1/elevation'
        headers = { 
            'Content-Type': 'application/json',
            'x-api-key': self.subscription_key,
            'Authorization': (f'Bearer {self.token}'),
            }
        # Iterate through list of GeoJSON features
        for i, feature in enumerate(self.loadedGeoJSON['features']):
            payload = json.dumps({
                "inVDatum": self.in_type,
                # "in_prj": self.in_prj,
                "zUnits": self.z_units,
                "geometry": self.loadedGeoJSON['features'][i]['geometry']
            })
            response = requests.request("POST", url, headers=headers, data=payload)
            self.carsGeoJSON = json.loads(response.text)
            # append GeoJSON with CARS attributes to geoJSONarr 
            self.geoJSONarr.append(self.carsGeoJSON)
        print(f'CARS Data Request Success Flight AGL: {self.agl} {self.z_units}')

    # Process CARS GeoJSON into final GeoJSON with altitude, agl, height_above_takeoff
    def addAglGeoJSON(self):
        '''With geoJSONarr from CARS function, calculate flight altitude
        :return: Prints success message e.g.
        Elevation Calculations Attributes Added
        :rtype: none
        '''       
        self.finalGeoJSON = []
        if type(self.geoJSONarr) is list:
            for i, geoJSON in enumerate(self.geoJSONarr):
                #    
                launchHeight = geoJSON['data']['features'][0]['properties']['terrainWGS84'] 
                for z, feature in enumerate(geoJSON['data']['features']):
                    altitude = feature['properties']['terrainWGS84'] + self.agl
                    geoJSON['data']['features'][z]['properties']['altitude'] = altitude
                    geoJSON['data']['features'][z]['properties']['AGL'] = self.agl
                    geoJSON['data']['features'][z]['properties']['height_above_takeoff'] = round((self.agl + (feature['properties']['terrainWGS84'] - launchHeight)), 2)
                self.finalGeoJSON.append(geoJSON['data'])
        print(f'Elevation Calculations Attributes Added')
    
    # save array of GeoJSON feature collections as KML with formatted attribute table
    def exportToWaypoints(self):
            '''Convert GeoJSON Feature Collection(s) into .waypoints QGroundControl format - version: QGC WPL 110
            The tab separated attributes are in the following order:
            'INDEX', 'CURRENT', 'COORD_FRAME', 'COMMAND', 'PARAM1', 'PARAM2', 'PARAM3', 'PARAM4', 'PARAM5/X/LATITUDE',
            'PARAM6/Y/LONGITUDE', 'PARAM7/Z/ALTITUDE', 'AUTOCONTINUE'
            PARAM1 - PARAM4 can be used to set aircraft flight attributes e.g. pitch, yaw, roll etc...
            :return: Prints success message and named of exported .waypoints file e.g. file saved as: waypointsTest.csv
            :rtype: Pandas DataFrame of flight waypoints with attributes as columns
            '''         
            # check if multiple GeoJSON Feature Collections
            if type(self.finalGeoJSON) is list:
                # iterate through each GeoJSON
                for z, geoJSON in enumerate(self.finalGeoJSON):
                    # Create header dfHead which contains QGC file version: QGC WPL 110
                    cols =['INDEX', 'CURRENT', 'COORD_FRAME', 'COMMAND', 'PARAM1', 'PARAM2','PARAM3','PARAM4',
                    'PARAM5/X/LATITUDE','PARAM6/Y/LONGITUDE','PARAM7/Z/ALTITUDE','AUTOCONTINUE']
                    dfHead = pd.DataFrame(columns=cols)
                    dfHead.loc[-1] = ['QGC', 'WPL', '110', '', '', '', '', '', '', '', '', '']
                    df = pd.DataFrame(columns=cols)
                    # concat the header dataframe and empty dataframe
                    df = pd.concat([df, dfHead])
                    for i, feat in enumerate(geoJSON['features']):
                        # add waypoints as dataframe records
                        # command=22 for aircraft takeoff - command=16 to proceed to next waypoint
                        command = 22 if i == 0 else 16
                        df.loc[i+1] = [str(i), str((i-1)), str(0), command, 0, 0, 0, 0, round(feat['geometry']['coordinates'][1], 8),
                                     round(feat['geometry']['coordinates'][0], 8), round(feat["properties"]["altitude"], 8), 1]
                    # command=21 for aircraft landing - insert at last waypoint
                    df.at[df.index[-1], 'COMMAND'] = 21
                    # save .waypoints file as tab separated text file
                    df.to_csv(f'{self.outName}.waypoints', sep ='\t', index=False, header=False)
                    print(f'file saved as: {self.outName}.waypoints')
                    return df

class Waypoints:

    def __init__(self, filePath: str, outputName: str, columnFormat: list, columnNames: list, 
                 lonCol: str, latCol: str, zCol: str):
        self.colSpecs, self.colNames, self.filePath, self.outputName = columnFormat,columnNames,filePath,outputName 
        self.lon, self.lat, self.z = lonCol, latCol, zCol
        self.df = pd.read_fwf(self.filePath, skiprows=1, colspecs=self.colSpecs, names=self.colNames)
        #self.df = df[(df[lonCol] != 0) | (df[latCol] != 0)]
        print(f'Loaded: {filePath} as DataFrame')

    def dfToGeoJSON(self):
        # example from https://notebook.community/captainsafia/nteract/applications/desktop/example-notebooks/pandas-to-geojson
        # empty python dictonary for GeoJSON
        self.geojson = {'type':'FeatureCollection', 'features':[]}
        for _, row in self.df.iterrows():
            # template for each feature
            feature = {'type':'Feature',
                        'properties':{},
                    'geometry':{'type':'Point',
                                'coordinates':[]}}
            feature['geometry']['coordinates'] = [ row[self.lon], row[self.lat], row[self.z] ]
            # add each column as GeoJSON property
            for prop in self.colNames:
                feature['properties'][prop] = row[prop]
            # append feature to Feature Collection
            self.geojson['features'].append(feature)
        print(f'Created GeoJSON dictonary from dataframe')

    def saveGeoJSON(self):
        # serialize GeoJSON object
        self.json_object = json.dumps(self.geojson, indent = 4)
        # create file timestamp
        self.timeStamp = time.strftime('%d%m%Y%H%M%S')
        # write GeoJSON output file
        with open((f'{self.outputName}_{self.timeStamp}.geojson'), "w") as outfile:
            outfile.write(self.json_object)
        print(f'GeoJSON output: {self.outputName}_{self.timeStamp}.geojson')
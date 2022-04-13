# install simplekml into active python environment
import subprocess
import sys
import os
import requests
import json
def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])    
install('simplekml')
import simplekml

class RouteToKML:
    '''This class ingests simplified GeoJSON output from the :class: 'CostPathFromSurface' class,
    first loading the GeoJSON file, then adding CARS elevation data to points via Airspace Link Azure function,
    next calculating the altitude from the CARS attributes and AGL parameter, then generating a kml file
    from the leastCostPath with both points, lines, and html popup descriptions. 
    Dependencies: requests, json, simplekml
    simplekml is required to generate kml outputs, in notebook run:
    !pip install simplekml -I

    :param geoJSONpath: path to GeoJSON file
    :type geoJSONpath: str
    :param z_units: ft or m 
    :type z_units: str
    :param agl: flight altitude Above Ground Level, units specified above
    :type agl: float
    :param outName: kml output filename
    :type outName: str

    # Example Workflow
    inputData = 'SampleRoutes_v2.geojson'
    z_units = 'ft'
    agl = 400
    outputName = 'PendletonRoutes'
    routes = RouteToKML(inputData, z_units, agl, outputName)
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
        self.exportToKML()          # Convert GeoJSON Feature Collection(s) into kml points and lines with attributes and add html popup/description
        '''        
        self.loadGeoJSON()
        self.addCARSdata()
        self.addAglGeoJSON()
        self.exportToKML()

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
    def exportToKML(self):
        '''Convert GeoJSON Feature Collection(s) into kml points and lines with attributes and add html popup/description
        :return: Prints success message and named of exported kml file e.g.
        PendletonRoutes0.kml - Saved Successfully
        :rtype: none
        '''         
        # check if multiple GeoJSON Feature Collections
        if type(self.finalGeoJSON) is list:
            # iterate through each GeoJSON
            for z, geoJSON in enumerate(self.finalGeoJSON):
                # Create new KML for each GeoJSON Route & new LineString coord list
                self.kml = simplekml.Kml()
                lineCoords = []
                # get conversion factor for KML altitude, value must be in meters
                self.conv = 1 if self.z_units == 'm' else (1 if self.z_units == 'meters' else .3048)
                # Loop through each Feature in Feature Collection
                for i, feat in enumerate(geoJSON['features']):
                    # Create new KML point for each feature
                    pnt = self.kml.newpoint(coords=[(feat['geometry']['coordinates'][0], feat['geometry']['coordinates'][1], (feat["properties"]["altitude"] * self.conv))])
                    # proceeding lines all construct KML/HTML popup for each feature
                    style1 = '<body style="margin:0px 0px 0px 0px;overflow:auto;background:#FFFFFF;height:100px">'
                    tableHead = '<table style="width:200px;border:1px solid black;font-family:Arial,Verdana,Times;font-size:14px;text-align:center;border-collapse:collapse;padding:3px 3px 3px 3px">'
                    table2 = '<table style="width:200px;border:1px solid black;font-family:Arial,Verdana,Times;font-size:12px;text-align:left;border-spacing:0px; padding:3px 3px 3px 3px">'
                    trHead = '<tr style="line-height:125%text-align:center;font-weight:bold;background:#9CBCE2;">'
                    trBack = '<tr style="line-height:110%" bgcolor="#D4E4F3">'
                    table_, tr, tr_, td, td_ = '</table>','<tr style="line-height:110%">','</tr>','<td>','</td>'
                    id,units,lon,lat= (f'{feat["id"]}'), (f'{feat["properties"]["units"]}'),(f'{round(feat["geometry"]["coordinates"][0],6)}'),(f'{round(feat["geometry"]["coordinates"][1],6)}')
                    alt, agl, hat = (f'{feat["properties"]["altitude"]}'), (f'{feat["properties"]["AGL"]}'), (f'{feat["properties"]["height_above_takeoff"]}')
                    line1 = (f"{style1}{tableHead}{trHead}{td}ID: {id}  -  UNITS: {units}{td_}{tr_}")
                    line2 = (f"{table2}{tr}{td}LON          {td_}{td}{td_}{td}{lon}{td_}{tr_}")
                    line3 = (f"{trBack}{td}LAT          {td_}{td}{td_}{td}{lat}{td_}{tr_}")
                    line4 = (f"{tr}{td}Flight Altitude {td_}{td}{td_}{td}{alt}{td_}{tr_}")
                    line5 = (f"{trBack}{td}AGL          {td_}{td}{td_}{td}{agl}{td_}{tr_}")
                    line6 = (f"{tr}{td}Height Above Takeoff {td_}{td}{td_}{td}{hat}{td_}{tr_}")
                    # Combine all of the lines for feature popup
                    pnt.description = (f'{line1}{line2}{line3}{line4}{line5}{line6}')
                    pnt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/paddle/blu-blank.png'
                    pnt.altitudemode = simplekml.AltitudeMode.absolute
                    pnt.style.iconstyle.hotspot = simplekml.HotSpot(x=0.5,y=0)
                    # collect coordinates to generate supplemental LineString
                    lineCoords.append((feat["geometry"]["coordinates"][0], feat["geometry"]["coordinates"][1], (feat["properties"]["altitude"] * self.conv)))
                line = self.kml.newlinestring(name=(f'{self.outName}{z}'), coords=lineCoords)
                # line style formatting
                line.style.linestyle.color,line.altitudemode,line.style.linestyle.width = 'ffff7000',simplekml.AltitudeMode.absolute,3
                self.kml.save(f'{self.outName}{z}.kml')
                print(f'{self.outName}{z}.kml - Saved Successfully')

    # # unit in either m, meters, ft, feet
    # def addZvalGeoJSON(inputGeoJSON, agl, units):
    #     geoJSONcopy = inputGeoJSON
    #     # check if unit conversion is needed
    #     units = str(units)
    #     agl = (agl*.3048) if units == 'ft' or units == 'feet' else agl
    #     # Loop through each feature in GeoJSON and add agl value to geometry for each coordinate pair
    #     for z, feature in enumerate(geoJSONcopy['features']):
    #         for i, coords in enumerate(feature['geometry']['coordinates']):
    #             newGeom = [coords[0],coords[1],agl]
    #             geoJSONcopy['features'][z]['geometry']['coordinates'][i] = newGeom
    #     # return GeoJSON with agl values added
    #     return geoJSONcopy
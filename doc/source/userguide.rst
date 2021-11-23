User Guide
==========

.. role:: raw-html(raw)
   :format: html

Inputs
------

To run RUBEM, several sets of input data are required. Check the :doc:`specification </fileformats>` and :doc:`preprocessing </preprocessing>` of the model's input files.

These input files are listed in a model configuration file that points to the locations of these input files and parameter sets that govern the simulation. Check a model configuration :ref:`template file <Configuration File Template>`.

Model General Settings
----------------------

Project Directories
```````````````````

Data Input Directory
''''''''''''''''''''

Mandatory path to dataset folder. Must be a valid path to an existing directory;

.. code-block:: dosini
   
   [DIRECTORIES]
   input = /Dataset/UIGCRB/

Data Output Directory
''''''''''''''''''''''

Mandatory path to the output folder. Must be a valid path to an existing **empty** directory.

.. code-block:: dosini
   
   [DIRECTORIES]
   output = /Dataset/UIGCRB/output/

Digital Elevation Map (DEM)
```````````````````````````

Mandatory path to Digital Elevation Map (DEM) file [masl] in:
   
 * **PCRaster map format** :file:`*.map`: this map contains topographic ground elevation in meters. Must be a valid file path to a PCRaster map format :file:`*.map` file;

 .. code-block:: dosini
    
    [RASTERS]
    dem = /Dataset/UIGCRB/input/maps/dem/dem.map

-------

 * **TIF format** :file:`*.tif`: this map contains topographic ground elevation in meters. Must be a valid file path to a TIF :file:`*.tif` raster file.

 .. code-block:: dosini
   
    [RASTERS]
    demtif = /Dataset/UIGCRB/input/maps/dem/dem.tif

Mask of Catchment (Clone)
``````````````````````````

Mandatory path to Mask of Catchment (Clone) file in PCRaster map format :file:`*.map`. This map defines the basin area to simulate in the model. Must be a valid file path to a PCRaster boolean map format  file;

.. code-block:: dosini
   
   [RASTERS]
   clone = /Dataset/UIGCRB/input/maps/clone/clone.map


Gauge Station Location Map
``````````````````````````

Export Results to Station Locations Map
'''''''''''''''''''''''''''''''''''''''

Optional, if enabled, export time series data of selected output variables (comma-separated values :file:`*.csv` files) for each valid pixel in stations maps. A station location map file must be defined;

.. code-block:: dosini
   
   [GENERATE_FILE]
   tss = True

Stations Locations (Samples)
''''''''''''''''''''''''''''

Mandatory if ``Export Results to Station Locations`` is enabled. Path to Stations file in PCRaster map format :file:`*.map` and nominal format. This file is a nominal map with unique Ids for cells identified as being a location where time-series output is required. Non-station cells have a value of ``-9999``. Must be a valid path to an existing PCRaster map format :file:`*.map` file.

.. code-block:: dosini
   
   [RASTERS]
   samples = /Dataset/UIGCRB/input/maps/postosFlu/stationsFluCalib.map

Grid
`````

Mandatory cell dimension value in meters. Value has to correspond to the pixel resolution of the dataset's DEM map file.

.. code-block:: dosini
   
   [GRID]
   grid = 500.0

Simulation Period
`````````````````

Start Date
''''''''''

Mandatory date of the first time step of the simulation scenario (month and year of the start period of simulation scenario);

.. code-block:: dosini
   
   [SIM_TIME]
   start = 01/01/2000

End Date
''''''''

Mandatory date of the last time step of the simulation scenario (month and year of the last period of simulation scenario).

.. code-block:: dosini
   
   [SIM_TIME]
   end = 01/08/2000

.. note::
   
   Both dates must be valid and fall within between the time period of the dataset input time scale. The ``end`` date must be greater than the ``start`` date.


Soil Parameters
----------------

Soil Map
````````

Mandatory path to Soil map in PCRaster map format :file:`*.map` and nominal format. It represents the soil classes of the study area. The number of classes is defined by the user and is related to hydraulic properties. Must be a valid path to an existing PCRaster map format :file:`*.map` file.

.. code-block:: dosini
   
   [RASTER]
   soil = /Dataset/UIGCRB/input/maps/soil/soil.map

Bulk Density
````````````

Mandatory path to a tabular file with values :raw-html:`[g/cm<sup>3</sup>]` of Bulk density for each soil class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   bulk_density = /Dataset/UIGCRB/input/txt/soil/dg.txt

:raw-html:`Saturated Hydraulic Conductivity (K<sub>SAT</sub>)`
````````````````````````````````````````````````````````````````````````````````

Mandatory path to a tabular file with values [mm/month] of saturated hydraulic conductivity for each soil class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   K_sat = /Dataset/UIGCRB/input/txt/soil/Tsat.txt

:raw-html:`Field Capacity (θ<sub>FC</sub>)`
`````````````````````````````````````````````````````````````

Mandatory path to a tabular file with values :raw-html:`[θ (cm<sup>3</sup>/cm<sup>3</sup>)]` of field capacity water content (θ) for each soil class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   T_fcap = /Dataset/UIGCRB/input/txt/soil/Tcc.txt

:raw-html:`Wilting Point (θ<sub>WP</sub>)`
```````````````````````````````````````````````````````````

Mandatory path to a tabular file with values :raw-html:`[θ (cm<sup>3</sup>/cm<sup>3</sup>)]` of Wilting Point for each soil class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   T_wp = /Dataset/UIGCRB/input/txt/soil/Tw.txt

:raw-html:`Saturated Content (θ<sub>SAT</sub>)`
````````````````````````````````````````````````````````````````

Mandatory path to a tabular file with values :raw-html:`[θ (cm<sup>3</sup>/cm<sup>3</sup>)]` of saturated content for each soil class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   T_sat = /Dataset/UIGCRB/input/txt/soil/Tsat.txt

Depth Rootzone
````````````````

Mandatory path to a tabular file with values [cm] of depth rootzone for each soil class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   rootzone_depth = /Dataset/UIGCRB/input/txt/soil/Zr.txt

Initial Soil Conditions
```````````````````````

Initial Baseflow
''''''''''''''''

Mandatory float value [mm] representing the baseflow at the beginning  of the simulation. It can be set by the rate of the flow rate in [L3T] and the grid cell dimension [L].

.. code-block:: dosini
   
   [INITIAL_SOIL_CONDITIONS]
   bfw_ini = 0.1

Baseflow Threshold
''''''''''''''''''

Mandatory float value [mm] representing the minimum water store in the saturated zone for generating Baseflow. It can be set by the rate of the monthly mean flow in [L3T] (from stream gauge) and the grid cell dimension [L] at dry season.

.. code-block:: dosini
   
   [INITIAL_SOIL_CONDITIONS]
   bfw_lim = 1.0

:raw-html:`Initial Soil Moisture Content (θ<sub>INI</sub>)`
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Mandatory float value :raw-html:`[θ (cm<sup>3</sup>/cm<sup>3</sup>)]` representing the Rootzone Soil Moisture Content value at the beginning of the simulation.

.. code-block:: dosini
   
   [INITIAL_SOIL_CONDITIONS]
   T_ini = 1.0

:raw-html:`Initial Saturated Zone Storage (S<sub>SAT</sub>)`
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Mandatory Saturated zone Moisture Content value [mm] at the beginning of the simulation. To generate Baseflow at the initial step this value must be greater than the baseflow threshold.

.. code-block:: dosini
   
   [INITIAL_SOIL_CONDITIONS]
   S_sat_ini = 1.0

Land Use Parameters
-------------------

Land Use Map-series
````````````````````

.. note::
   
   The map-series consists of a spatial map for each time-step in the model. This means if the model has 100 monthly time-steps, 100 maps of land-use are mandatory.
   
   A map-series in PCRaster always starts with the :file:`*.001` extension, corresponding with the start date of your model simulation period. According to `PCRaster documentation <https://pcraster.geo.uu.nl/pcraster/4.3.1/documentation/python_modelling_framework/PCRasterPythonFramework.html#pcraster.framework.frameworkBase.generateNameT>`_ the name of each of the files in the series should have eight characters before the dot, and 3 characters after the dot. The name of each map starts with a prefix, and ends with the number of the time step. All characters in between are filled with zeroes.

Mandatory path to a directory containing the land use map-series. The directory containing these files must contain the maps that representing the mean monthly LUC, where each map represents the variable's value at a particular time step. If some \*.00\* file is missing, the map of the previous step will be used. Must be a valid path to an existing directory. Note that it is also necessary to indicate the prefix of the filenames of the series.

.. code-block:: dosini
   
   [DIRECTORIES]
   landuse = /Dataset/UIRB/input/maps/landuse/

   [FILENAME_PREFIXES]
   landuse_prefix = ldu


Manning's Roughness Coefficient
````````````````````````````````

Mandatory path to a tabular file with values of Manning's roughness coefficient values for each land-use class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   manning = /Dataset/UIGCRB/input/txt/landuse/manning.txt

:raw-html:`Maximum Leaf Area Index (LAI<sub>MAX</sub>)`
````````````````````````````````````````````````````````````````````````

Mandatory maximum float value [dimensionless quantity] that characterizes plant canopies. It is defined as the one-sided green leaf area per unit ground surface area. 

.. math:: 1 \leq LAI_{MAX} \leq 12

.. code-block:: dosini
   
   [CONSTANTS]
   lai_max = 12.0

:raw-html:`Impervious Area Interception (I<sub>I</sub>)`
``````````````````````````````````````````````````````````````````````````

Mandatory float value [mm] that represents the rainfall interception in impervious areas.

.. math:: 1 < I_I < 3

.. code-block:: dosini
   
   [CONSTANTS]
   i_imp = 2.5

Normalized Difference Vegetation Index (NDVI)
`````````````````````````````````````````````

NDVI Map-series
''''''''''''''''

.. note::

   The map-series consists of a spatial map for each time-step in the model. This means if the model has 100 monthly time-steps, 100 maps of NDVI are mandatory.
   
   A map-series in PCRaster always starts with the :file:`*.001` extension, corresponding with the start date of your model simulation period. According to `PCRaster documentation <https://pcraster.geo.uu.nl/pcraster/4.3.1/documentation/python_modelling_framework/PCRasterPythonFramework.html#pcraster.framework.frameworkBase.generateNameT>`_ the name of each of the files in the series should have eight characters before the dot, and 3 characters after the dot. The name of each map starts with a prefix, and ends with the number of the time step. All characters in between are filled with zeroes.

Mandatory path to a directory containing the land use map-series. The directory containing these files must contain the maps that representing the mean monthly LUC, where each map represents the variable's value at a particular time step. If some \*.00\* file is missing, the map of the previous step will be used. Must be a valid path to an existing directory. Note that it is also necessary to indicate the prefix of the filenames of the series.

Mandatory path to a directory containing the monthly Normalized Difference Vegetation Index (NDVI) map-series format. The directory containing these files must contain the maps representing the mean monthly NDVI, where each map represents the variable's value at a particular time step. If some \*.00\* file is missing, the map of the previous step will be used. Must be a valid path to an existing directory. Note that it is also necessary to indicate the prefix of the filenames of the series.

.. code-block:: dosini
   
   [FILES]
   ndvi = /Dataset/UIRB/input/maps/ndvi/

   [FILENAME_PREFIXES]
   ndvi_prefix = ndvi

Maximum NDVI Map
'''''''''''''''''

Mandatory path to maximum NDVI file in PCRaster map format :file:`*.map`. This file is a scalar pcraster map with values for each cell, representing the maximum value of NDVI in the historic series available for the cell. Must be a valid path to an existing PCRaster map format :file:`*.map` file.

.. code-block:: dosini
   
   [RASTERS]
   ndvi_max = /Dataset/UIGCRB/input/maps/ndvi/ndvi_max.map

Minimum NDVI Map
''''''''''''''''

Mandatory path to minimum NDVI file in PCRaster map format :file:`*.map`. This file is a scalar pcraster map with values for each cell, representing the minimum value of NDVI in the historic series available for the cell. Must be a valid path to an existing PCRaster map format :file:`*.map` file.

.. code-block:: dosini
   
   [RASTERS]
   ndvi_min = /Dataset/UIGCRB/input/maps/ndvi/ndvi_min.map

Area Fractions
``````````````

Impervious Area Fraction (ai)
''''''''''''''''''''''''''''''

Mandatory path to file with values of fraction of impervious surface area values for each land-use class. This file is a text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv` with values, representing the fraction of impervious surface area for each land-use class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   a_i = /Dataset/UIGCRB/input/txt/landuse/a_i.txt

Open Water Area Fraction (ao)
'''''''''''''''''''''''''''''' 

Mandatory path to file with values of fraction of open-water area values for each land-use class. This file is a text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv` with values, representing the fraction of open-water area for each land-use class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   a_o = /Dataset/UIGCRB/input/txt/landuse/a_o.txt

Bare Soil Area Fraction (as)
'''''''''''''''''''''''''''''

Mandatory path to file with values of fraction of bare soil area values for each land-use class. This file is a text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv` with values, representing the fraction of bare soil area for each land-use class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   a_s = /Dataset/UIGCRB/input/txt/landuse/a_s.txt

Vegetated Area Fraction (av) 
''''''''''''''''''''''''''''

Mandatory path to file with values of fraction of vegetated area values for each land-use class. This file is a text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv` with values, representing the fraction of vegetated area for each land-use class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   a_v = /Dataset/UIGCRB/input/txt/landuse/a_v.txt


Crop Coefficient (K\ :sub:`C`\)
```````````````````````````````

:raw-html:`Maximum (K<sub>C</sub>)`
''''''''''''''''''''''''''''''''''''''''''''''''''''

Mandatory path to a tabular file with values of maximum crop coefficient for each land-use class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   K_c_max = /Dataset/UIGCRB/input/txt/landuse/kcmax.txt

:raw-html:`Minimum (K<sub>C</sub>)`
''''''''''''''''''''''''''''''''''''''''''''''''''''

Mandatory path to a tabular file with values of minimum crop coefficient for each land-use class. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   K_c_min = /Dataset/UIGCRB/input/txt/landuse/kcmin.txt

Fraction Photosynthetically Active Radiation (FPAR)
```````````````````````````````````````````````````

.. math:: 0 \leq FPAR_{MAX} \leq 1

.. math:: FPAR_{MAX} > FPAR_{MIN}

Maximum FPAR
''''''''''''''

Mandatory maximum float value [dimensionless quantity] of fraction photosynthetically active radiation. This parameter is related to the maximum Leaf Area Index and allows the calculation of canopy storage.

.. code-block:: dosini
   
   [CONSTANTS]
   fpar_max = 0.95

Minimum FPAR
'''''''''''''

Mandatory minimum float value [dimensionless quantity] of fraction photosynthetically active radiation. This parameter is related to the minimum Leaf Area Index and allows the calculation of canopy storage.

.. code-block:: dosini
   
   [CONSTANTS]
   fpar_min = 0.001



Climate Data Series
--------------------

.. note::
   
   The map-series consists of a spatial map for each time-step in the model. This means if the model has 100 monthly time-steps, 100 maps of rainfall/:raw-html:`ET<sub>P</sub>`/:raw-html:`K<sub>P</sub>` are mandatory.
   
   A map-series in PCRaster always starts with the :file:`*.001` extension, corresponding with the start date of your model simulation period. According to `PCRaster documentation <https://pcraster.geo.uu.nl/pcraster/4.3.1/documentation/python_modelling_framework/PCRasterPythonFramework.html#pcraster.framework.frameworkBase.generateNameT>`_ the name of each of the files in the series should have eight characters before the dot, and 3 characters after the dot. The name of each map starts with a prefix, and ends with the number of the time step. All characters in between are filled with zeroes.

:raw-html:`Monthly Rainfall (P<sub>M</sub>)`
````````````````````````````````````````````

Mandatory path to a directory containing the Monthly Rainfall map-series format [mm/month]. The directory containing these files must contain the maps representing the variable's value at a particular time step the mean monthly :raw-html:`P<sub>M</sub>`, where each map represents the variable's value at a particular time step. If some \*.00\* file is missing, the map of the previous step will be used. Must be a valid path to an existing directory. Note that it is also necessary to indicate the prefix of the filenames of the series.

.. code-block:: dosini

   [FILES]
   prec = /Dataset/UIRB/input/maps/prec/

   [FILENAME_PREFIXES]
   prec_prefix = prec

:raw-html:`Monthly Potential Evapotranspiration (ET<sub>P</sub>)`
``````````````````````````````````````````````````````````````````

Mandatory path to a directory containing the Monthly Potential Evapotranspiration map-series format [mm/month]. The directory containing these files must contain the maps representing the mean monthly :raw-html:`ET<sub>P</sub>`, where each map represents the variable's value at a particular time step. If some \*.00\* file is missing, the map of the previous step will be used. Must be a valid path to an existing directory. Note that it is also necessary to indicate the prefix of the filenames of the series.

.. code-block:: dosini
   
   [FILES]
   etp = /Dataset/UIRB/input/maps/etp/

   [FILENAME_PREFIXES]
   etp_prefix = etp

:raw-html:`Class A Pan Coefficient (K<sub>P</sub>)`
````````````````````````````````````````````````````

Mandatory path to a directory containing the Class A Pan Coefficient map-series format[mm/month]. The directory containing these files must contain the maps representing the mean monthly :raw-html:`K<sub>P</sub>`, where each map represents the variable's value at a particular time step. If some \*.00\* file is missing, the map of the previous step will be used. Must be a valid path to an existing directory. Note that it is also necessary to indicate the prefix of the filenames of the series.

.. code-block:: dosini
   
   [FILES]
   kp = /Dataset/UIRB/input/maps/kp/

   [FILENAME_PREFIXES]
   kp_prefix = kp

Monthly Rainy Days
```````````````````

Mandatory path to a tabular file [days/month] with values representing the mean value of rainy days for each month of the simulation period. Must be a valid path to an existing text file :file:`*.txt` or comma-separated values (CSV) file :file:`*.csv`.

.. code-block:: dosini
   
   [TABLES]
   rainydays = /Dataset/UIGCRB/input/txt/rainydays.txt

Model Parameters
-----------------

Interception Parameter (α)
``````````````````````````

Mandatory float value [dimensionless quantity] that affects the daily interception threshold that depends on land use.

.. math:: 0.01 \leq \alpha \leq 10

Surface runoff is directly related to interception, an optimal value can be obtained by calibration surface runoff against direct runoff separated from streamflow observations.

.. code-block:: dosini
   
   [CALIBRATION]
   alpha = 4.5

Rainfall Intensity Coefficient (b)
``````````````````````````````````

Mandatory float exponent value [dimensionless quantity]  that represents the effect of rainfall intensity in the runoff.

.. math:: 0.01 \leq b \leq 1

The value is higher for low rainfall intensities resulting in less surface runoff, and approaches to one for high rainfall intensities. If :math:`b = 1`, a linear relationship is assumed between rainfall excess and soil moisture.

.. code-block:: dosini
   
   [CALIBRATION]
   b = 0.5

Regional Consecutive Dryness Level (RCD)
`````````````````````````````````````````

Mandatory float value [mm] that incorporates the intensity of rain and the number of consecutive days in runoff calculation.

.. math:: 0 \leq RCD \leq 10

:math:`RCD = 1.0` can be used for very heavy or torrential rainfall and more than 10 consecutive rainy days/month, and :math:`RCD = 10.0` for low regional intensity rainfall less than 2 consecutive rainy days per month.

.. code-block:: dosini
   
   [CALIBRATION]
   rcd = 5.0

Flow Direction Factor (f)
``````````````````````````

Mandatory float value [dimensionless quantity] used to partition the flow out of the root zone between interflow and flow to the saturated zone.

.. math:: 0.01 \leq f \leq 1

:math:`f = 1.0` corresponds to a 100% horizontal flow direction, and :math:`f = 0` corresponds to a 100% vertical flow direction.

.. code-block:: dosini
   
   [CALIBRATION]
   f = 0.5

:raw-html:`Soil Factor Weigh (w<sub>2</sub>)`
````````````````````````````````````````````````````````````````````````````

Mandatory float value [dimensionless quantity] that relates the baseflow response to changes in groundwater recharge. 

.. math:: 0.01 \leq \alpha_{GW} \leq 1

Therefore, lower values for :math:`\alpha_{GW}` therefore correspond to areas that respond slowly to groundwater recharge, whereas higher values indicate areas that rapidly respond to groundwater recharge.

.. code-block:: dosini
   
   [CALIBRATION]
   alpha_gw = 0.5

Flow Recession Coefficient (x)
````````````````````````````````
  
Mandatory float value [dimensionless quantity] that incorporates a flow delay in the accumulated amount of water that flows out of the cell into its neighboring downstream cell.

.. math:: 0 \leq x \leq 1

:math:`x \approx 0` corresponds to a fast responding catchment, and :math:`x \approx 1` corresponds to a slow responding catchment.

.. code-block:: dosini
   
   [CALIBRATION]
   x = 0.5

Weight Factors
``````````````

:raw-html:`Soil Factor Weigh (w<sub>2</sub>)``
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Mandatory float value [dimensionless quantity] that contributes to calculating permeables areas runoff, and is related to the Manning coefficient for each land use class. It measures the effect of the land use on the potential runoff produced. 

.. code-block:: dosini
   
   [CALIBRATION]
   w_1 = 0.333

:raw-html:`Soil Factor Weigh (w<sub>2</sub>)`
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Mandatory float value [dimensionless quantity] that contributes to calculating permeables area runoff, and is related to wilting points for each soil class. It measures the effect of the soil class on the potential runoff produced.

.. code-block:: dosini
   
   [CALIBRATION]
   w_2 = 0.333

:raw-html:`Soil Factor Weigh (w<sub>2</sub>)`
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Mandatory float value [dimensionless quantity] that contributes to calculating of permeables areas runoff, and is related to pixel slope. It measures the effect of the slope on the potential runoff produced.

.. code-block:: dosini
   
   [CALIBRATION]
   w_3 = 0.334

:math:`w_1`, :math:`w_2` and :math:`w_3` are the weight factors for the three components contributing to the runoff coefficient for permeable areas, used in surface runoff formulation. Their sum must be equal to 1.

.. math:: w_1 + w_2 + w_3 = 1 

Model Output Formats
---------------------

At least one of these two options must be set to ``True`` to define the format of the generated raster files. The default format option is PCRaster map format ``map_raster_series = True``.

PCRaster Map Format
````````````````````

Default ``True`` boolean, the raster data generated by the model will be exported in PCRaster map format. See the `related documentation <https://gdal.org/drivers/raster/pcraster.html>`__ for more information.

.. code-block:: dosini

   [RASTER_FILE_FORMAT]
   map_raster_series = True
 

TIFF/GeoTIFF
````````````

Default ``True`` boolean, the raster data generated by the model will be exported in TIFF/GeoTIFF map format. See the `related documentation <https://gdal.org/drivers/raster/gtiff.html>`__ for more information.

.. code-block:: dosini

   [RASTER_FILE_FORMAT]
   tiff_raster_series = True
 

Model Output Parameters
------------------------

.. warning::
   At least one output variable must be enabled for the respective time series raster files to be generated.

.. note::
   If ``genTss`` option is enabled and a valid ``samples`` raster is provided, a comma-separated values (CSV) file :file:`*.csv` will be generated for each of the enabled options. The :file:`*.csv` file is structured as follows: each row represents a time step and each column represents a measurement station, and the cell data represents the value of the respective pixel in the selected raster map.

Total Interception
``````````````````

Optional boolean value. If enabled, this option allows the generation of Total Interception (ITP) [mm] result maps in raster format for each of the time steps included in the simulation period.

.. code-block:: dosini
   
   [GENERATE_FILE]
   itp = True

Baseflow
````````

Optional boolean value. If enabled, this option allows the generation of  Baseflow (BFW) [mm] result maps in raster format for each of the time steps included in the simulation period.

.. code-block:: dosini
   
   [GENERATE_FILE]
   bfw = True

Surface Runoff
``````````````

Optional boolean value. If enabled, this option allows the generation of  Surface runoff (SRN) [mm] result maps in raster format for each of the time steps included in the simulation period.

.. code-block:: dosini
   
   [GENERATE_FILE]
   srn = True

Actual Evapotranspiration
``````````````````````````

Optional boolean value. If enabled, this option allows the generation of Actual Evapotranspiration (ETA) [mm] result maps in raster format for each of the time steps included in the simulation period.


.. code-block:: dosini
   
   [GENERATE_FILE]
   eta = True

Lateral Flow
````````````

Optional boolean value. If enabled, this option allows to generate  the resulting maps of Lateral Flow (LFW) [mm] result maps in raster format for each of the time steps included in the simulation period.

.. code-block:: dosini
   
   [GENERATE_FILE]
   lfw = True

Recharge
`````````

Optional boolean value. If enabled, this option allows the generation of Recharge (REC) [mm] result maps in raster format for each of the time steps included in the simulation period.

.. code-block:: dosini
   
   [GENERATE_FILE]
   rec = True

Soil Moisture Content
``````````````````````

Optional boolean value. If enabled, this option allows the generation of Soil Moisture Content (SMC) [mm] result maps in raster format for each of the time steps included in the simulation period.

.. code-block:: dosini
   
   [GENERATE_FILE]
   smc = True

Total Runoff
````````````
  
Optional boolean value. If enabled, this option allows the generation of Total Runoff [:raw-html:`m<sup>3</sup>s<sup>-1</sup>`] result maps in raster format for each of the time steps included in the simulation period.

.. code-block:: dosini
   
   [GENERATE_FILE]
   rnf = True

Configuration File Template
---------------------------

.. code-block:: dosini

   [SIM_TIME]
   start = 01/01/2000
   end = 01/02/2000

   [DIRECTORIES]
   input = /Dataset/UIRB/
   output = /Dataset/UIRB/output/
   etp = /Dataset/UIRB/input/maps/etp/
   prec = /Dataset/UIRB/input/maps/prec/
   ndvi = /Dataset/UIRB/input/maps/ndvi/
   Kp = /Dataset/UIRB/input/maps/kp/
   landuse = /Dataset/UIRB/input/maps/landuse/

   [FILENAME_PREFIXES]
   etp_prefix = etp
   prec_prefix = prec
   ndvi_prefix = ndvi
   kp_prefix = kp
   landuse_prefix = ldu

   [RASTERS]
   dem = /Dataset/UIRB/input/maps/dem/dem.map
   demtif = /Dataset/UIRB/input/maps/dem/dem.tif
   clone = /Dataset/UIRB/input/maps/clone/clone.map
   ndvi_max = /Dataset/UIRB/input/maps/ndvi/ndvi_max.map
   ndvi_min = /Dataset/UIRB/input/maps/ndvi/ndvi_min.map
   soil = /Dataset/UIRB/input/maps/soil/soil.map
   samples = /Dataset/UIRB/input/maps/samples/samples.map

   [TABLES]
   rainydays = /Dataset/UIRB/input/tables/rainydays.txt
   a_i = /Dataset/UIRB/input/tables/landuse/a_i.txt
   a_o = /Dataset/UIRB/input/tables/landuse/a_o.txt
   a_s = /Dataset/UIRB/input/tables/landuse/a_s.txt
   a_v = /Dataset/UIRB/input/tables/landuse/a_v.txt
   manning = /Dataset/UIRB/input/tables/landuse/manning.txt
   bulk_density = /Dataset/UIRB/input/tables/soil/dg.txt
   K_sat = /Dataset/UIRB/input/tables/soil/Kr.txt
   T_fcap = /Dataset/UIRB/input/tables/soil/Tcc.txt
   T_sat = /Dataset/UIRB/input/tables/soil/Tsat.txt
   T_wp = /Dataset/UIRB/input/tables/soil/Tw.txt
   rootzone_depth = /Dataset/UIRB/input/tables/soil/Zr.txt
   K_c_min = /Dataset/UIRB/input/tables/landuse/kcmin.txt
   K_c_max = /Dataset/UIRB/input/tables/landuse/kcmax.txt


   [GRID]
   grid = 500.0

   [CALIBRATION]
   alpha = 4.5
   b = 0.5
   w_1 = 0.333
   w_2 = 0.333
   w_3 = 0.334
   rcd = 5.0
   f = 0.5
   alpha_gw = 0.5
   x = 0.5

   [INITIAL_SOIL_CONDITIONS]
   T_ini = 1.0
   bfw_ini = 0.1
   bfw_lim = 1.0
   S_sat_ini = 1.0

   [CONSTANTS]
   fpar_max = 0.95
   fpar_min = 0.001
   lai_max = 12.0
   i_imp = 2.5

   [GENERATE_FILE]
   itp = True
   bfw = True
   srn = True
   eta = True
   lfw = True
   rec = True
   smc = True
   rnf = True
   tss = True

   [RASTER_FILE_FORMAT]
   map_raster_series = True
   tiff_raster_series = True

------------------

Running RUBEM
-------------

When running RUBEM without any arguments, you will see the following message on your console:

.. code-block:: console

   $ python rubem.py
   usage: RUBEM [-h] --configfile CONFIGFILE [--version] [--verbose]
   RUBEM: error: the following arguments are required: --configfile

Command Line Options
````````````````````

Use ``-h`` or ``--help`` to get a brief description of RUBEM and each argument.

.. code-block:: console

   $ python rubem.py --help
   usage: RUBEM [-h] --configfile CONFIGFILE [--version] [--verbose]

   Rainfall rUnoff Balance Enhanced Model (RUBEM)

   optional arguments:
   -h, --help            show this help message and exit
   --configfile CONFIGFILE
                           path to configuration file
   --version, -V         show program's version number and exit
   --verbose, -v         set the verbosity level

   Developed by LabSid-PHA-EPUSP 

Use ``-V`` or ``--version`` to get the version of the RUBEM.

.. code-block:: console

   $ python rubem.py --version
   RUBEM v0.1.0

Use ``-c`` or ``--configfile`` to set the path of the RUBEM configuration file.

.. code-block:: console

   $ python rubem.py --configfile project-config.ini
   RUBEM::Started
   RUBEM::Reading configuration file... OK
   RUBEM::Running dynamic model...
   RUBEM::Reading input files... OK
   .Time: 1
         Interception... OK
         Evapotranspiration... OK
         Surface Runoff... OK
         Lateral Flow... OK
         Recharge Flow... OK
         Baseflow... OK
         Soil Balance... OK
         Runoff... OK
   Exporting variables to files... OK
   Ending cycle 1 of 2
   .Time: 2
         Interception... OK
         Evapotranspiration... OK
         Surface Runoff... OK
         Lateral Flow... OK
         Recharge Flow... OK
         Baseflow... OK
         Soil Balance... OK
         Runoff... OK
   Exporting variables to files... OK
   Ending cycle 2 of 2
   RUBEM::Dynamic model runtime: 3.28 seconds
   RUBEM::Converting *.tss files to *.csv... OK
   RUBEM::Finished     

Tutorials
=========

Alto Iguaçu River Basin Minimal Example
----------------------------------------

In this section an example of application of the model in the Brazilian basin of the Alto Iguaçu river is presented. For this case study you need to download the respective required dataset which is available on the :doc:`datasets page </datasets>`.

For this example, we will set up the RUBEM model for ten years: 2000 to 2009. For this period, we will set up a 500 x 500 m spatial resolution (grid cell size). All maps used in this tutorial are in the WGS 84 ESPG 2346 projection. In this tutorial, each step to set up the model is discussed. 

Create a new project
`````````````````````

Create a new project in the downloaded dataset directory named :file:`Iguazu.ini` or another appropriate filename. 
 
.. _initial-settings:

Initial Settings
````````````````

Open the created :file:`Iguazu.ini` file and enter the following fields into the file to specify a directory to store the model output files. The output directory is the directory where the model will store the results:

.. code-block:: dosini
   
   [DIRECTORIES]
   output = /Iguazu/output/

Enable ``Export results to station locations (tss)`` option to export of results at the locations of the gauging stations as CSV files. Then define the file containing the map of the stations locations ``samples``:

.. code-block:: dosini
    
    [GENERATE_FILE]
    tss = True

    [RASTERS]
    samples = /Iguazu/maps/stations/samples.map


Now let's fill in the other fields with the appropriate maps from the input directory (Dataset :file:`maps` folder), as indicated in the table below:

+----------------------------------------------------------+
| Model General settings                                   |
+===========+==============================================+
| DEM MAP   | :file:`/Iguazu/maps/dem/dem.map`             |
+-----------+----------------------------------------------+
| DEM TIFF  | :file:`/Iguazu/maps/dem/dem.tif`             |
+-----------+----------------------------------------------+
| Clone MAP | :file:`/Iguazu/maps/clone/clone.map`         |
+-----------+----------------------------------------------+

In the part ``Grid`` set 500.000 m as size value and in the part Simulation Period, set the ``start`` and ``end`` of the simulation, from January 2000 until December 2009.

.. code-block:: dosini

    [GRID]
    grid = 500.00

    [SIM_TIME]
    start = 01/01/2000
    end = 01/12/2009

    [DIRECTORIES]
    output = /Iguazu/output/

    [GENERATE_FILE]
    tss = True

    [RASTERS]
    dem = /Iguazu/input/maps/dem/dem.map
    demtif = /Iguazu/input/maps/dem/dem.tif
    clone = /Iguazu/input/maps/clone/clone.map
    samples = /Iguazu/maps/stations/samples.map  

Soil settings
``````````````

In the Soil Parameters input maps and tables need to be provided for different physical soil parameters. Soil raster data are located at :file:`/input/maps/soil/`. Define ``soil`` as :file:`/input/maps/soil/soil.map`. This map has the soil types in the basin. The numerical values in this map correspond to the categorized soil types defined from the Brazilian Soil Classification System. 

The folder :file:`/input/txt/soil` contains tables with the values of the soil parameters coupled to each soil type. Select the corresponding table at each field (e.g. :file:`/input/txt/soil/Ksat.txt` in Saturated Hydraulic Conductivity). 

Set the following values for ``Initial Soil Conditions`` fields:

+------------------------------------------+
| Initial Soil Conditions                  |
+================================+=========+
| Initial Baseflow               | ``10``  |
+--------------------------------+---------+
| Baseflow Threshold             | ``150`` |
+--------------------------------+---------+
| Initial Saturated Zone Storage | ``151`` |
+--------------------------------+---------+
| Initial Soil Moisture Content  | ``0.5`` |
+--------------------------------+---------+

.. code-block:: dosini

    [GRID]
    grid = 500.00

    [SIM_TIME]
    start = 01/01/2000
    end = 01/12/2009

    [DIRECTORIES]
    output = /Iguazu/output/

    [GENERATE_FILE]
    tss = True

    [RASTERS]
    dem = /Iguazu/input/maps/dem/dem.map
    demtif = /Iguazu/input/maps/dem/dem.tif
    clone = /Iguazu/input/maps/clone/clone.map
    samples = /Iguazu/maps/stations/samples.map 
    soil =  /Iguazu/input/maps/soil/soil.map

    [TABLES]
    bulk_density = /Iguazu/input/txt/soil/Bdens.txt
    K_sat = /Iguazu/input/txt/soil/Ksat.txt
    T_fcap = /Iguazu/input/txt/soil/Tfc.txt
    T_sat = /Iguazu/input/txt/soil/Tsat.txt
    T_wp = /Iguazu/input/txt/soil/Twp.txt
    rootzone_depth = /Iguazu/input/txt/soil/Dpz.txt

    [INITIAL_SOIL_CONDITIONS]
    T_ini = 0.5
    bfw_ini = 10.0
    bfw_lim = 150.0
    S_sat_ini = 151.0

Land Use settings
``````````````````
 
Land Use data are located at :file:`/input/maps/landuse/` and :file:`/input/maps/ndvi/` directories. These directories contain input maps (map-series) for landuse and NDVI. The filenames in :file:`ndvi` folder have a strict numbering format: :file:`ndvi0000.001` until :file:`ndvi0000.228` in a monthly base. In folder :file:`landuse`, files correspond to annual maps, :file:`cov00000.001` – :file:`cov00000.013`. For landuse, RUBEM use the prior map when map correspond to current timestep (1 - Jan/2000 to 132-Dec/2010) is this example) does not exist in the directory.
 
Select :file:`cov00000.001` as ``Land Use map series``, :file:`ndvi0000.001` for ``Normalized Difference Vegetation Index`` and the corresponds :file:`.map` for maximum and minimum NDVI. 
 
Similar to the soil tab, the folder :file:`/input/txt/landuse` contains tables with the values of the land use parameters coupled to each cover type, select the corresponding table at each field (e.g. :file:`/input/txt/landuse/manning.txt` in Manning file). 

Use the default values for ``FPAR``, ``LAI`` and ``Impervious Area Interception``.

+------------------------------+-----------+
| Default Values                           |
+==============================+===========+
| FPAR Maximum                 | ``0.950`` |
+------------------------------+-----------+
| FPAR Minimum                 | ``0.001`` |
+------------------------------+-----------+
| LAI Maximum                  | ``12.0``  |
+------------------------------+-----------+
| Impervious Area Interception | ``2.5``   |
+------------------------------+-----------+

.. code-block:: dosini

    [GRID]
    grid = 500.00

    [SIM_TIME]
    start = 01/01/2000
    end = 01/12/2009

    [DIRECTORIES]
    output = /Iguazu/output/
    ndvi = /Iguazu/input/maps/ndvi/
    landuse = /Iguazu/input/maps/landuse/

    [FILENAME_PREFIXES]
    ndvi_prefix = ndvi
    landuse_prefix = cov    

    [GENERATE_FILE]
    tss = True

    [RASTERS]
    dem = /Iguazu/input/maps/dem/dem.map
    demtif = /Iguazu/input/maps/dem/dem.tif
    clone = /Iguazu/input/maps/clone/clone.map
    samples = /Iguazu/maps/stations/samples.map 
    soil =  /Iguazu/input/maps/soil/soil.map
    ndvi_max = /Iguazu/input/maps/ndvi/ndvi_max.map
    ndvi_min = /Iguazu/input/maps/ndvi/ndvi_min.map    

    [TABLES]
    bulk_density = /Iguazu/input/txt/soil/Bdens.txt
    K_sat = /Iguazu/input/txt/soil/Ksat.txt
    T_fcap = /Iguazu/input/txt/soil/Tfc.txt
    T_sat = /Iguazu/input/txt/soil/Tsat.txt
    T_wp = /Iguazu/input/txt/soil/Twp.txt
    rootzone_depth = /Iguazu/input/txt/soil/Dpz.txt
    a_i = /Iguazu/input/txt/landuse/a_i.txtF
    a_o = /Iguazu/input/txt/landuse/a_o.txt
    a_s = /Iguazu/input/txt/landuse/a_s.txt
    a_v = /Iguazu/input/txt/landuse/a_v.txt
    manning = /Iguazu/input/txt/landuse/manning.txt
    K_c_min = /Iguazu/input/txt/landuse/kcmin.txt
    K_c_max = /Iguazu/input/txt/landuse/kcmax.txt


    [INITIAL_SOIL_CONDITIONS]
    T_ini = 0.5
    bfw_ini = 10.0
    bfw_lim = 150.0
    S_sat_ini = 151.0

    [CONSTANTS]
    fpar_max = 0.950
    fpar_min = 0.001
    lai_max = 12.000
    i_imp = 2.500

Climate settings
`````````````````
 
In the ``Climate`` section define the appropriate map-series from :file:`/input/maps/prec/` for ``Precipitation [mm/month]``, :file:`/input/maps/etp/` for ``Potential Evapotranspiration [mm/month]``, and :file:`/input/maps/kp/` for ``Class A Pan Coefficient [-]``. In the ``Rainy days`` section select the appropriate file from :file:`/input/txt/`. It should be noted that the start date always has to correspond with the first climate forcing file (:file:`*.001`).

.. code-block:: dosini

    [GRID]
    grid = 500.00

    [SIM_TIME]
    start = 01/01/2000
    end = 01/12/2009

    [DIRECTORIES]
    output = /Iguazu/output/
    ndvi = /Iguazu/input/maps/ndvi/
    landuse = /Iguazu/input/maps/landuse/
    etp = /Iguazu/input/maps/etp/
    prec = /Iguazu/input/maps/prec/
    kp = /Iguazu/input/maps/kp/

    [FILENAME_PREFIXES]
    etp_prefix = etp
    prec_prefix = prec
    kp_prefix = kp
    ndvi_prefix = ndvi    
    landuse_prefix = cob  

    [GENERATE_FILE]
    tss = True

    [RASTERS]
    dem = /Iguazu/input/maps/dem/dem.map
    demtif = /Iguazu/input/maps/dem/dem.tif
    clone = /Iguazu/input/maps/clone/clone.map
    samples = /Iguazu/maps/stations/samples.map 
    soil =  /Iguazu/input/maps/soil/soil.map
    ndvi_max = /Iguazu/input/maps/ndvi/ndvi_max.map
    ndvi_min = /Iguazu/input/maps/ndvi/ndvi_min.map    

    [TABLES]
    rainydays = /Iguazu/input/txt/rainydays.txt
    bulk_density = /Iguazu/input/txt/soil/Bdens.txt
    K_sat = /Iguazu/input/txt/soil/Ksat.txt
    T_fcap = /Iguazu/input/txt/soil/Tfc.txt
    T_sat = /Iguazu/input/txt/soil/Tsat.txt
    T_wp = /Iguazu/input/txt/soil/Twp.txt
    rootzone_depth = /Iguazu/input/txt/soil/Dpz.txt
    a_i = /Iguazu/input/txt/landuse/a_i.txt
    a_o = /Iguazu/input/txt/landuse/a_o.txt
    a_s = /Iguazu/input/txt/landuse/a_s.txt
    a_v = /Iguazu/input/txt/landuse/a_v.txt
    manning = /Iguazu/input/txt/landuse/manning.txt
    K_c_min = /Iguazu/input/txt/landuse/kcmin.txt
    K_c_max = /Iguazu/input/txt/landuse/kcmax.txt


    [INITIAL_SOIL_CONDITIONS]
    T_ini = 0.5
    bfw_ini = 10.0
    bfw_lim = 150.0
    S_sat_ini = 151.0

    [CONSTANTS]
    fpar_max = 0.950
    fpar_min = 0.001
    lai_max = 12.000
    i_imp = 2.500

Parameters Settings
````````````````````

Values in this tab correspond to calibrated parameters in the basin. For the dataset, the figure below shows the values. The model calibration requires a trial and error approach when RUBEM Hydrological (plugin) is the only tool used. It is possible to adapt RUBEM (code) for using optimization tools for calibration e.g. `Scipy library algorithms <https://scipy.org>`__. 

+-------------------------------------------+-----------+
| Parameter                                 | Value     |
+===========================================+===========+
| Interception Parameter (alpha)            | ``4.410`` |
+-------------------------------------------+-----------+
| Rainfall Intensity Coefficient (b)        | ``0.07``  |
+-------------------------------------------+-----------+
| Land Use Factor Weight (w_1)              | ``0.51``  |
+-------------------------------------------+-----------+
| Soil Factor Weight (w_2)                  | ``0.12``  |
+-------------------------------------------+-----------+
| Slope Factor Weight (w_3)                 | ``0.37``  |
+-------------------------------------------+-----------+
| Regional Consecutive Dryness Level (rcd)  | ``5.37``  |
+-------------------------------------------+-----------+
| Flow Direction Factor (f)                 | ``0.58``  |
+-------------------------------------------+-----------+
| Baseflow Recession Coefficient (alpha_GW) | ``0.92``  |
+-------------------------------------------+-----------+
| Flow Recession Coefficient (x)            | ``0.307`` |
+-------------------------------------------+-----------+

.. code-block:: dosini

    [GRID]
    grid = 500.00

    [SIM_TIME]
    start = 01/01/2000
    end = 01/12/2009

    [DIRECTORIES]
    output = /Iguazu/output/
    ndvi = /Iguazu/input/maps/ndvi/
    landuse = /Iguazu/input/maps/landuse/
    etp = /Iguazu/input/maps/etp/
    prec = /Iguazu/input/maps/prec/
    kp = /Iguazu/input/maps/kp/

    [FILENAME_PREFIXES]
    etp_prefix = etp
    prec_prefix = prec
    kp_prefix = kp
    ndvi_prefix = ndvi    
    landuse_prefix = cob  

    [GENERATE_FILE]
    tss = True

    [RASTERS]
    dem = /Iguazu/input/maps/dem/dem.map
    demtif = /Iguazu/input/maps/dem/dem.tif
    clone = /Iguazu/input/maps/clone/clone.map
    samples = /Iguazu/maps/stations/samples.map 
    soil =  /Iguazu/input/maps/soil/soil.map
    ndvi_max = /Iguazu/input/maps/ndvi/ndvi_max.map
    ndvi_min = /Iguazu/input/maps/ndvi/ndvi_min.map    

    [TABLES]
    rainydays = /Iguazu/input/txt/rainydays.txt
    bulk_density = /Iguazu/input/txt/soil/Bdens.txt
    K_sat = /Iguazu/input/txt/soil/Ksat.txt
    T_fcap = /Iguazu/input/txt/soil/Tfc.txt
    T_sat = /Iguazu/input/txt/soil/Tsat.txt
    T_wp = /Iguazu/input/txt/soil/Twp.txt
    rootzone_depth = /Iguazu/input/txt/soil/Dpz.txt
    a_i = /Iguazu/input/txt/landuse/a_i.txt
    a_o = /Iguazu/input/txt/landuse/a_o.txt
    a_s = /Iguazu/input/txt/landuse/a_s.txt
    a_v = /Iguazu/input/txt/landuse/a_v.txt
    manning = /Iguazu/input/txt/landuse/manning.txt
    K_c_min = /Iguazu/input/txt/landuse/kcmin.txt
    K_c_max = /Iguazu/input/txt/landuse/kcmax.txt


    [INITIAL_SOIL_CONDITIONS]
    T_ini = 0.5
    bfw_ini = 10.0
    bfw_lim = 150.0
    S_sat_ini = 151.0

    [CONSTANTS]
    fpar_max = 0.950
    fpar_min = 0.001
    lai_max = 12.000
    i_imp = 2.500

    [CALIBRATION]
    alpha = 4.41
    b = 0.07
    w1 = 0.51
    w2 = 0.12
    w3 = 0.37
    rcd = 5.37
    f = 0.58
    alpha_gw = 0.92
    x = 0.307


Model Execution Settings
````````````````````````

Within this section it's necessary to specify for each variable if you want this to be reported as model output ``True`` or ``False``. The ``Generate Files`` Section contais a list with all the variables that can be reported as model output.

In the example below  it can be seen that ``Recharge``, ``Accumulated Total Runoff`` and ``Total Interception`` are checked to be reported. If ``Export Results to stations locations (tss)``  was defined as ``True``, time-series for the selected variables will be generated.

The default format the generated raster files is PCRaster map format ``map_raster_series = True``.

The complete project configuration file should look like this:

.. code-block:: dosini

    [GRID]
    grid = 500.00

    [SIM_TIME]
    start = 01/01/2000
    end = 01/12/2009

    [DIRECTORIES]
    output = /Iguazu/output/
    ndvi = /Iguazu/input/maps/ndvi/
    landuse = /Iguazu/input/maps/landuse/
    etp = /Iguazu/input/maps/etp/
    prec = /Iguazu/input/maps/prec/
    kp = /Iguazu/input/maps/kp/

    [FILENAME_PREFIXES]
    etp_prefix = etp
    prec_prefix = prec
    kp_prefix = kp
    ndvi_prefix = ndvi    
    landuse_prefix = cob  

    [RASTERS]
    dem = /Iguazu/input/maps/dem/dem.map
    demtif = /Iguazu/input/maps/dem/dem.tif
    clone = /Iguazu/input/maps/clone/clone.map
    samples = /Iguazu/maps/stations/samples.map 
    soil =  /Iguazu/input/maps/soil/soil.map
    ndvi_max = /Iguazu/input/maps/ndvi/ndvi_max.map
    ndvi_min = /Iguazu/input/maps/ndvi/ndvi_min.map    

    [TABLES]
    rainydays = /Iguazu/input/txt/rainydays.txt
    bulk_density = /Iguazu/input/txt/soil/Bdens.txt
    K_sat = /Iguazu/input/txt/soil/Ksat.txt
    T_fcap = /Iguazu/input/txt/soil/Tfc.txt
    T_sat = /Iguazu/input/txt/soil/Tsat.txt
    T_wp = /Iguazu/input/txt/soil/Twp.txt
    rootzone_depth = /Iguazu/input/txt/soil/Dpz.txt
    a_i = /Iguazu/input/txt/landuse/a_i.txt
    a_o = /Iguazu/input/txt/landuse/a_o.txt
    a_s = /Iguazu/input/txt/landuse/a_s.txt
    a_v = /Iguazu/input/txt/landuse/a_v.txt
    manning = /Iguazu/input/txt/landuse/manning.txt
    K_c_min = /Iguazu/input/txt/landuse/kcmin.txt
    K_c_max = /Iguazu/input/txt/landuse/kcmax.txt


    [INITIAL_SOIL_CONDITIONS]
    T_ini = 0.5
    bfw_ini = 10.0
    bfw_lim = 150.0
    S_sat_ini = 151.0

    [CONSTANTS]
    fpar_max = 0.950
    fpar_min = 0.001
    lai_max = 12.000
    i_imp = 2.500

    [CALIBRATION]
    alpha = 4.41
    b = 0.07
    w1 = 0.51
    w2 = 0.12
    w3 = 0.37
    rcd = 5.37
    f = 0.58
    alpha_gw = 0.92
    x = 0.307

    [GENERATE_FILE]
    itp = True
    bfw = False
    srn = False
    eta = False
    lfw = False
    rec = True
    smc = False
    rnf = False
    arn = True
    tss = True    

    [RASTER_FILE_FORMAT]
    map_raster_series = True
    tiff_raster_series = False

In a proper Conda environment, run the following command:

.. code-block:: console
    
    $ python rubem -c Iguazu.ini

If all the project's configuration file is specified correctly, the user should be faced with the following:

.. code-block:: console
    
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
    Ending cycle 1 of 122

    [This part was purposely omitted because of limited space]

    .Time: 120
        Interception... OK
        Evapotranspiration... OK
        Surface Runoff... OK
        Lateral Flow... OK
        Recharge Flow... OK
        Baseflow... OK
        Soil Balance... OK
        Runoff... OK
    Exporting variables to files... OK
    Ending cycle 120 of 120
    RUBEM::Dynamic model runtime: 9.38 seconds
    RUBEM::Converting *.tss files to *.csv... OK
    RUBEM::Finished

The files generated by the model will be in the directory specified in the ``output`` parameter.

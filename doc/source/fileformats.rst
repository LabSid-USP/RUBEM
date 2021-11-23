File Formats
============

.. role:: raw-html(raw)
   :format: html


Input File Formats
------------------

Mask of Catchment (Clone) raster
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This file is the result of pre-processing the corresponding TIFF/GeoTIFF raster file through PCRASTER library.

- Filetype: PCRaster map format :file:`*.map` raster file.
- Unit: boolean
- Restriction: 

  - ``PCRASTER_VALUESCALE`` = ``VS_boolean``

- Dimensions:

  - It depends on the result of rasterization of the study area. The clone resolution depends on the availability of the DEM resolution and has as content the simulated basin. 

Digital Elevation Map (DEM) raster
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This file is the result of pre-processing the corresponding TIFF/GeoTIFF raster file through PCRASTER library.

- Filetype: PCRaster map format :file:`*.map` raster file.
- Unit: Scalar
- Restrictions: 

  - ``PCRASTER_VALUESCALE`` = ``VS_SCALAR``;
  - The file cannot contain a missing value for each pixel that is ``True`` (has a boolean 1 value) on the mask map.

- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Digital Elevation Map (DEM) raster (TIFF)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: TIFF :file:`*.tif` raster file.
- Unit: Scalar
- Restriction: 

- Dimensions:

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.


Potential Evapotranspiration (:raw-html:`ET<sub>P</sub>`) raster series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These files are the result of pre-processing the TIFF/GeoTIFF raster file series through PCRASTER library.

- Filetype: PCRaster map format (:file:`etp00000.001`- :file:`etp99999.999` raster map series).
- Unit: mm/month
- Restriction: 

  - The file cannot contain a missing value for each pixel that is ``True`` (has a boolean 1 value) on the mask map;
  - Each month of the historical series corresponds to a :raw-html:`ET<sub>P</sub>` file.

- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

.. note::

    The map-series consists of a spatial map for each time-step in the model. This means if the model has 100 monthly time-steps, 100 maps of Potential Evapotranspiration are mandatory. 
    
    A map-series in PCRaster always starts with the :file:`*.001` extension, corresponding with the star date of your model simulation period. 
    
    The format of each individual forcing file should have eight characters before the dot, and 3 characters after the dot. The name of each map starts with a prefix, and ends with the number of the time step. All characters in between are filled with zeroes. `Related PCRaster documentation <https://pcraster.geo.uu.nl/pcraster/4.3.1/documentation/python_modelling_framework/PCRasterPythonFramework.html#pcraster.framework.frameworkBase.generateNameT>`__.


Rainfall (:raw-html:`P<sub>M</sub>`) raster series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These files are the result of pre-processing the TIFF/GeoTIFF raster file series through PCRASTER library.

- Filetype: PCRaster map format (:file:`raf00000.001`- :file:`raf99999.999` raster map series). 
- Unit: mm/month
- Restriction: 

  - The file cannot contain a missing value for each pixel that is ``True`` (has a boolean 1 value) on the mask map;
  - Each month of the historical series corresponds to a rainfall file.

- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

.. note::

    The map-series consists of a spatial map for each time-step in the model. This means if the model has 100 monthly time-steps, 100 maps of rainfall are mandatory. 
    
    A map-series in PCRaster always starts with the :file:`*.001` extension, corresponding with the star date of your model simulation period. 
    
    The format of each individual forcing file should have eight characters before the dot, and 3 characters after the dot. The name of each map starts with a prefix, and ends with the number of the time step. All characters in between are filled with zeroes. `Related PCRaster documentation <https://pcraster.geo.uu.nl/pcraster/4.3.1/documentation/python_modelling_framework/PCRasterPythonFramework.html#pcraster.framework.frameworkBase.generateNameT>`__.


Normalized Difference Vegetation Index (NDVI) raster series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These files are the result of pre-processing the TIFF/GeoTIFF raster file series through PCRASTER library.

- Filetype: PCRaster map format (:file:`ndvi0000.001`- :file:`ndvi9999.999` raster map series).
- Unit: Dimensionless
- Restriction: 

  - The file cannot contain a missing value for each pixel that is ``True`` (has a boolean 1 value) on the mask map;
  - Each month of the historical series corresponds to a NDVI file.

- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

.. note::

    The map-series consists of a spatial map for each time-step in the model. This means if the model has 100 monthly time-steps, 100 maps of NDVI are mandatory. 
    
    A map-series in PCRaster always starts with the :file:`*.001` extension, corresponding with the star date of your model simulation period. 
    
    The format of each individual forcing file should have eight characters before the dot, and 3 characters after the dot.The name of each map starts with a prefix, and ends with the number of the time step. All characters in between are filled with zeroes. `Related PCRaster documentation <https://pcraster.geo.uu.nl/pcraster/4.3.1/documentation/python_modelling_framework/PCRasterPythonFramework.html#pcraster.framework.frameworkBase.generateNameT>`__.


Class A Pan Coefficient (:raw-html:`K<sub>P</sub>`) raster series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These files are the result of pre-processing the TIFF/GeoTIFF raster file series through PCRASTER library. 

:raw-html:`K<sub>P</sub>` is interpolated by kriging of weather stations.

- Filetype: PCRaster map format (:file:`kpc00000.001`- :file:`kpc99999.999` raster map series).
- Unit: Dimensionless
- Restriction: 

  - The file cannot contain a missing value for each pixel that is ``True`` (has a boolean 1 value) on the mask map;
  - Each month of the historical series corresponds to a :raw-html:`K<sub>P</sub>` file.

- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

.. note::

    The map-series consists of a spatial map for each time-step in the model. This means if the model has 100 monthly time-steps, 100 maps of Kp are mandatory. 
    
    A map-series in PCRaster always starts with the :file:`*.001` extension, corresponding with the star date of your model simulation period. 
    
    The format of each individual forcing file should have eight characters before the dot, and 3 characters after the dot. The name of each map starts with a prefix, and ends with the number of the time step. All characters in between are filled with zeroes. `Related PCRaster documentation <https://pcraster.geo.uu.nl/pcraster/4.3.1/documentation/python_modelling_framework/PCRasterPythonFramework.html#pcraster.framework.frameworkBase.generateNameT>`__.


Land Use raster series
^^^^^^^^^^^^^^^^^^^^^^^

These files are the result of pre-processing the TIFF/GeoTIFF raster file series through PCRASTER library.

- Filetype: PCRaster map format (:file:`luc00000.001`- :file:`luc99999.999` raster map series).
- Unit: Nominal
- Restrictions: 

  - ``PCRASTER_VALUESCALE`` = ``VS_NOMINAL``;
  - The file cannot contain a missing value for each pixel that is ``True`` (has a boolean 1 value) on the mask map;
  - A cover file is required for each timestep of the historical series.

- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

.. note::

    The map-series consists of a spatial map for each time-step in the model. This means if the model has 100 monthly time-steps, 100 maps of land use are mandatory. 
    
    A map-series in PCRaster always starts with the :file:`*.001` extension, corresponding with the star date of your model simulation period. 
    
    The format of each individual forcing file should have eight characters before the dot, and 3 characters after the dot. The name of each map starts with a prefix, and ends with the number of the time step. All characters in between are filled with zeroes. `Related PCRaster documentation <https://pcraster.geo.uu.nl/pcraster/4.3.1/documentation/python_modelling_framework/PCRasterPythonFramework.html#pcraster.framework.frameworkBase.generateNameT>`__.

Soil raster
^^^^^^^^^^^^

This file is the result of pre-processing the corresponding TIFF/GeoTIFF raster file through PCRASTER library.

- Filetype: PCRaster map format :file:`*.map` raster file.
- Unit: Nominal
- Restrictions: 

  - ``PCRASTER_VALUESCALE`` = ``VS_NOMINAL``;
  - The file cannot contain a missing value for each pixel that is ``True`` (has a boolean 1 value) on the mask map.

- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Stations (samples) raster
^^^^^^^^^^^^^^^^^^^^^^^^^^

This file is the result of pre-processing the corresponding TIFF/GeoTIFF raster file through PCRASTER library.

- Filetype: PCRaster map format :file:`*.map` raster file.
- Unit: Nominal
- Restriction: 

  - ``PCRASTER_VALUESCALE`` = ``VS_NOMINAL``

- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Maximum NDVI raster
^^^^^^^^^^^^^^^^^^^^

This file is the result of pre-processing the corresponding TIFF/GeoTIFF raster file through PCRASTER library.

- Filetype: PCRaster map format :file:`*.map` raster file.
- Unit: Dimensionless
- Restrictions: 

  - ``PCRASTER_VALUESCALE`` = ``VS_SCALAR``;
  - The file cannot contain a missing value for each pixel that is ``True`` (has a boolean 1 value) on the mask map.

- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Minimum NDVI raster
^^^^^^^^^^^^^^^^^^^^

This file is the result of pre-processing the corresponding TIFF/GeoTIFF raster file through PCRASTER library.

- Filetype: PCRaster map format :file:`*.map` raster file.
- Unit:Dimensionless
- Restrictions: 

  - ``PCRASTER_VALUESCALE`` = ``VS_SCALAR``;
  - The file cannot contain a missing value for each pixel that is ``True`` (has a boolean 1 value) on the mask map.

- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Monthly Rainy Days table
^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: rainy days/month
- Restriction: 

  - 12 values, one for each month (mean value historic series)

- Dimensions: 
  
  - Rows = 12;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Month Number
     - Rainy Days

   * - Int <1-12>
     - Int <1-31>

Impervious Area Fraction (:raw-html:`a<sub>i</sub>`) table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: Dimensionless
- Restriction: 

  - :math:`a_i + a_o + a_s + a_v = 1`

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Coverage Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Open Water Area Fraction (:raw-html:`a<sub>o</sub>`) table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: Dimensionless
- Restriction: 

  - :math:`a_i + a_o + a_s + a_v = 1`

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Coverage Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Bare Soil Area Fraction (:raw-html:`a<sub>s</sub>`) table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: Dimensionless
- Restriction: 

  - :math:`a_i + a_o + a_s + a_v = 1`

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Coverage Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Vegetated Area Fraction (:raw-html:`a<sub>v</sub>`) table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: Dimensionless
- Restriction: 

  - :math:`a_i + a_o + a_s + a_v = 1`

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Coverage Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Manning's Roughness Coefficient table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: Dimensionless
- Restriction: 
    
  - One value for each soil class.

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Coverage Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Bulk Density table
^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: :raw-html:`g/cm<sup>3</sup>`
- Restriction: 

  - One value for each soil class.

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Soil Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Saturated Hydraulic Conductivity (:raw-html:`K<sub>SAT</sub>`) table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: mm/month
- Restriction: 

  - One value for each soil class.

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Soil Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Field Capacity (:raw-html:`θ<sub>FC</sub>`) table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: :raw-html:`θ (cm<sup>3</sup>/cm<sup>3</sup>)`
- Restriction: 

  - One value for each soil class.

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Soil Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Saturated Content (:raw-html:`θ<sub>SAT</sub>`) table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: :raw-html:`θ (cm<sup>3</sup>/cm<sup>3</sup>)`
- Restriction: 

  - One value for each soil class.

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Soil Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Wilting Point (:raw-html:`θ<sub>WP</sub>`) table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: :raw-html:`θ (cm<sup>3</sup>/cm<sup>3</sup>)`
- Restriction: 
    
  - One value for each soil class..

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Soil Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Depth Rootzone table
^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: cm

- Restriction: 
 
  - One value for each soil class..

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Soil Type
     - Value

   * - Int <1-\*>
     - Float <\*>

Minimum Crop Coefficient (:raw-html:`K<sub>C<sub>MIN</sub></sub>`) table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: Dimensionless

- Restriction: 

  - :math:`K_{C_{MAX}} > K_{C_{MIN}}`

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Coverage Type
     - Value

   * - Int <1-\*>
     - Float <\*>


Maximum Crop Coefficient (:raw-html:`K<sub>C<sub>MAX</sub></sub>`) table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Filetype: Text :file:`*txt` or Comma-separated values (CSV) :file:`*.csv` file.
- Unit: Dimensionless

- Restriction: 

  - :math:`K_{C_{MAX}} > K_{C_{MIN}}`

- Dimensions: 

  - Rows =  Number of land use classes;
  - Columns = 2.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Coverage Type
     - Value

   * - Int <1-\*>
     - Float <\*>


Output File Formats
-------------------

Total Interception raster series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Resulting maps of Total Interception (ITP) [mm]  in raster format for all simulation period for each pixel of :ref:`stations map <Stations (samples) raster>`.

- Filetype: PCRaster map format (:file:`itp00000.001`- :file:`itp99999.999` raster map series).
- Unit: mm
- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Baseflow raster series
^^^^^^^^^^^^^^^^^^^^^^^

Resulting maps of  Baseflow (BFW) [mm]  in raster format for all simulation period or for each pixel of :ref:`stations map <Stations (samples) raster>`.

- Filetype: PCRaster map format (:file:`bfw00000.001`- :file:`bfw99999.999` raster map series).
- Unit: mm
- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Surface Runoff raster series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Resulting maps of  Surface runoff (SRN) [mm] in raster format for all simulation period or for each pixel of :ref:`stations map <Stations (samples) raster>`.

- Filetype: PCRaster map format (:file:`srn00000.001`- :file:`srn99999.999` raster map series).
- Unit: mm
- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Actual Evapotranspiration raster series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Resulting maps of Actual Evapotranspiration (ETA) [mm] in raster format for all simulation period or for each pixel of :ref:`stations map <Stations (samples) raster>`.

- Filetype: PCRaster map format (:file:`eta00000.001`- :file:`eta99999.999` raster map series).
- Unit: mm
- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Lateral Flow raster series
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Resulting maps of Lateral Flow (LFW) [mm] in raster format for all simulation period for each pixel of :ref:`stations map <Stations (samples) raster>`.

- Filetype: PCRaster map format (:file:`lfw00000.001`- :file:`lfw99999.999` raster map series).
- Unit: mm
- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Recharge raster series
^^^^^^^^^^^^^^^^^^^^^^^

Resulting maps of Recharge (REC) [mm] in raster format for all simulation period or for each pixel of :ref:`stations map <Stations (samples) raster>`.

- Filetype: PCRaster map format (:file:`rec00000.001`- :file:`rec99999.999` raster map series).
- Unit: mm
- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Soil Moisture Content raster series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Resulting maps of Soil Moisture Content (SMC) [mm] in raster format for all simulation period or for each pixel of :ref:`stations map <Stations (samples) raster>`.

- Filetype: PCRaster map format (:file:`smc00000.001`- :file:`smc99999.999` raster map series).
- Unit: mm
- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Total Runoff raster series
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Resulting maps of Total Runoff [:raw-html:`m<sup>3</sup>s<sup>-1</sup>`] in raster format for all simulation period for each pixel of :ref:`stations map <Stations (samples) raster>`.

- Filetype: PCRaster map format (:file:`rnf00000.001`- :file:`rnf99999.999` raster map series).
- Unit: :raw-html:`m<sup>3</sup>s<sup>-1</sup>`
- Dimensions: 

  - Rows = :ref:`clone rows <Mask of Catchment (Clone) raster>`;
  - Columns = :ref:`clone columns<Mask of Catchment (Clone) raster>`;
  - Cell Size = :ref:`clone cell size<Mask of Catchment (Clone) raster>`.

Total Interception table
^^^^^^^^^^^^^^^^^^^^^^^^^

Resulting values of Total Interception (ITP) [mm] in table format for all simulation period for each sampling station present in :ref:`stations map <Stations (samples) raster>`.

- Filetype: Comma-Separated Values (CSV) :file:`*.csv`
- Unit: mm
- Dimensions: 

  - Rows = number of time steps;
  - Columns = number of sampling stations from the station map.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Time Step
     - Station #1 
     - Station #2
     - `...`
     - Station #N          

   * - 1 
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>

   * - `...`
     - `...`
     - `...`
     - `...`
     - `...`

   * - N
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>                  

Baseflow table
^^^^^^^^^^^^^^^

Resulting maps of  Baseflow (BFW) [mm] in table format for all simulation period for each sampling station present in :ref:`stations map <Stations (samples) raster>`.

- Filetype: Comma-Separated Values (CSV) :file:`*.csv`
- Unit: mm
- Dimensions: 

  - Rows = number of time steps;
  - Columns = number of sampling stations from the station map.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Time Step
     - Station #1 
     - Station #2
     - `...`
     - Station #N          

   * - 1 
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>

   * - `...`
     - `...`
     - `...`
     - `...`
     - `...`

   * - N
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>    

Surface Runoff table
^^^^^^^^^^^^^^^^^^^^^

Resulting maps of  Surface runoff (SRN) [mm] in table format for all simulation period for each sampling station present in :ref:`stations map <Stations (samples) raster>`.

- Filetype: Comma-Separated Values (CSV) :file:`*.csv`
- Unit: mm
- Dimensions: 

  - Rows = number of time steps;
  - Columns = number of sampling stations from the station map.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Time Step
     - Station #1 
     - Station #2
     - `...`
     - Station #N          

   * - 1 
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>

   * - `...`
     - `...`
     - `...`
     - `...`
     - `...`

   * - N
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>    

Actual Evapotranspiration table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Resulting maps of Actual Evapotranspiration (ETA) [mm] in table format for all simulation period for each sampling station present in :ref:`stations map <Stations (samples) raster>`.

- Filetype: Comma-Separated Values (CSV) :file:`*.csv`
- Unit: mm
- Dimensions: 

  - Rows = number of time steps;
  - Columns = number of sampling stations from the station map.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Time Step
     - Station #1 
     - Station #2
     - `...`
     - Station #N          

   * - 1 
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>

   * - `...`
     - `...`
     - `...`
     - `...`
     - `...`

   * - N
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>    

Lateral Flow table
^^^^^^^^^^^^^^^^^^^

Resulting maps of Lateral Flow (LFW) [mm] in table format for all simulation period for each sampling station present in :ref:`stations map <Stations (samples) raster>`.

- Filetype: Comma-Separated Values (CSV) :file:`*.csv`
- Unit: mm
- Dimensions: 

  - Rows = number of time steps;
  - Columns = number of sampling stations from the station map.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Time Step
     - Station #1 
     - Station #2
     - `...`
     - Station #N          

   * - 1 
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>

   * - `...`
     - `...`
     - `...`
     - `...`
     - `...`

   * - N
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>    

Recharge table
^^^^^^^^^^^^^^^

Resulting maps of Recharge (REC) [mm] in table format for all simulation period for each sampling station present in :ref:`stations map <Stations (samples) raster>`.

- Filetype: Comma-Separated Values (CSV) :file:`*.csv`
- Unit: mm
- Dimensions: 

  - Rows = number of time steps;
  - Columns = number of sampling stations from the station map.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Time Step
     - Station #1 
     - Station #2
     - `...`
     - Station #N          

   * - 1 
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>

   * - `...`
     - `...`
     - `...`
     - `...`
     - `...`

   * - N
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>    

Soil Moisture Content table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Resulting maps of Soil Moisture Content (SMC) [mm] in table format for all simulation period for each sampling station present in :ref:`stations map <Stations (samples) raster>`.

- Filetype: Comma-Separated Values (CSV) :file:`*.csv`
- Unit: mm
- Dimensions: 

  - Rows = number of time steps;
  - Columns = number of sampling stations from the station map.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Time Step
     - Station #1 
     - Station #2
     - `...`
     - Station #N          

   * - 1 
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>

   * - `...`
     - `...`
     - `...`
     - `...`
     - `...`

   * - N
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>    

Total Runoff table
^^^^^^^^^^^^^^^^^^^

Resulting maps of Total Runoff [:raw-html:`m<sup>3</sup>s<sup>-1</sup>`] in table format for all simulation period for each sampling station present in :ref:`stations map <Stations (samples) raster>`.

- Filetype: Comma-Separated Values (CSV) :file:`*.csv`
- Unit: :raw-html:`m<sup>3</sup>s<sup>-1</sup>`
- Dimensions: 

  - Rows = number of time steps;
  - Columns = number of sampling stations from the station map.

.. list-table:: Basic file structure:
   :header-rows: 1

   * - Time Step
     - Station #1 
     - Station #2
     - `...`
     - Station #N          

   * - 1 
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>

   * - `...`
     - `...`
     - `...`
     - `...`
     - `...`

   * - N
     - Float <\*>
     - Float <\*>
     - `...`
     - Float <\*>    
Installation
============

RUBEM depends on `PCRaster <https://pcraster.geo.uu.nl/>`__ and
`GDAL <https://gdal.org/>`__, which are distributed through
`conda-forge <https://conda-forge.org/>`__. Create the runtime environment
first and install RUBEM into it with pip.

Requirements
------------

- Python 3.12 or later
- A conda-compatible package manager (Miniconda, Miniforge or micromamba)

From the repository
-------------------

1. Get the source code, either by cloning the repository or by downloading
   and extracting the archive of the latest release from the
   `releases page <https://github.com/LabSid-USP/RUBEM/releases>`__:

   .. code-block:: console

      git clone https://github.com/LabSid-USP/RUBEM.git
      cd RUBEM

2. Create and activate the runtime environment, with conda:

   .. code-block:: console

      conda env create -f environment.yml
      conda activate rubem

   or with micromamba, which has no ``conda`` command:

   .. code-block:: console

      micromamba create -f environment.yml -y
      micromamba activate rubem

3. Install RUBEM into the environment:

   .. code-block:: console

      pip install .

Running the model
-----------------

With the environment active, the ``rubem`` command is available anywhere:

.. code-block:: console

   rubem -h
   rubem -c config.json

Development installs
--------------------

For working on RUBEM itself, install in editable mode with the development
extras:

.. code-block:: console

   pip install -e '.[dev]'

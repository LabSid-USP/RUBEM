Groundwater Coupling with MODFLOW
=================================

.. role:: raw-html(raw)
   :format: html

RUBEM represents the saturated zone of each cell as a lumped linear reservoir:
the recharge fills it and the baseflow :math:`BFW` drains it with the
recession coefficient :math:`\alpha_{GW}` (see
:ref:`overview:Calibration and Validation`). A basin whose regional aquifer,
river-aquifer exchange or lateral boundaries matter cannot be represented that
way. The optional MODFLOW section replaces that reservoir by a
three-dimensional groundwater flow model, MODFLOW-2005 [HARBAUGH2005]_, run
through the MODFLOW extension of PCRaster (``pcraster.initialise``).

The coupling is **opt-in**. A configuration without the section, or with the
section and ``"enabled": false``, runs exactly as before: nothing of this page
applies to it, and RUBEM does not even load its groundwater module. A section
present but disabled is reported as ignored (a non-blocking problem); its keys
must still be keys of the section, but its rules and its files are not
checked.

This page documents what the coupling exchanges, the configuration keys and
their units, the rules the configuration and the inputs must follow, what the
run writes, and the limitations of the coupling. The keys are also listed,
section by section, in the :ref:`user guide <userguide:MODFLOW Groundwater Coupling>`.

What the coupling exchanges
---------------------------

One step, one stress period
```````````````````````````

Every RUBEM time step is one MODFLOW stress period. RUBEM steps are months, so
the length of a period, :math:`\Delta t`, is the number of days of the month
of the step; in a transient run the period is divided into ``dis.nstp`` time
steps. The groundwater model is built once, when the simulation starts, and
kept for the whole run: the heads of a period are the initial heads of the
next one.

Recharge
````````

The recharge RUBEM computes for the step (the ``rec`` output variable, in
millimetres per step) is given to the MODFLOW recharge package (RCH) as a flux
in metres per day:

.. math::
   :label: groundwater-recharge
   :nowrap:

    \[R_{MF} = \frac{REC}{1000 \cdot \Delta t}\]

where:

- :math:`R_{MF}` – recharge flux given to MODFLOW [m/day];
- :math:`REC` – recharge of the step computed by RUBEM [mm];
- :math:`\Delta t` – length of the stress period [days].

A cell without recharge (missing value) receives none. The recharge is applied
to the highest active cell of each column (RCH option ``NRCHOP = 3``).

Baseflow
````````

The river package (RIV) exchanges water between the aquifer and the river
cells. The leakage that leaves the aquifer towards the river is the baseflow
of the step: it replaces the baseflow of the lumped reservoir and keeps the
output variable ``bfw`` and its unit, millimetres per step.

.. math::
   :label: groundwater-baseflow
   :nowrap:

    \[BFW = \frac{1000 \cdot \Delta t}{A} \sum_{k} \max\left(-Q_{RIV,k},\ 0\right)\]

where:

- :math:`BFW` – baseflow of the step [mm];
- :math:`Q_{RIV,k}` – RIV leakage of the cell in layer :math:`k`, positive
  into the aquifer [:raw-html:`m<sup>3</sup>day<sup>-1</sup>`]; the sum runs
  over the layers that hold river cells;
- :math:`A` – area of a RUBEM cell, the square of ``GRID.grid``
  (``raster_info.grid_size`` in format 1.0) [:raw-html:`m<sup>2</sup>`];
- :math:`\Delta t` – length of the stress period [days].

The baseflow enters the total runoff of the cell as it does without MODFLOW.
The leakage in the opposite direction, from the river into the aquifer, is
reported (``mfrv2aq``, see `Outputs of a coupled run`_) but is not taken from
any RUBEM flux.

The saturated zone
``````````````````

While MODFLOW is coupled it holds the saturated zone: the lumped reservoir of
RUBEM is not updated, and the baseflow recession equation is not evaluated.
The parameters and initial conditions that only feed that reservoir,
``alpha_gw`` (``CALIBRATION``) and ``bfw_ini``, ``bfw_lim`` and ``S_sat_ini``
(``INITIAL_SOIL_CONDITIONS``), remain mandatory keys of the configuration and
are still validated, but they have no effect on a coupled run.

Boundaries that shape the heads
```````````````````````````````

General-head boundaries (GHB), drains (DRN) and the rewetting of dry cells
(BCF wetting) change the heads, and through them the river leakage, but none of
their flows is returned to RUBEM.

Requirements
------------

The coupling needs two things that the conda-forge ``pcraster`` package
installs with PCRaster itself, so no other package is needed:

- the PCRaster MODFLOW extension, the module ``pcraster._pcraster_modflow``;
- the MODFLOW-2005 executable ``mf2005``, which the extension starts.

The extension looks for ``mf2005`` on ``PATH``. When the environment is used
without being activated it is not there, so RUBEM also looks next to the
interpreter, in ``<prefix>/bin/mf2005`` (or ``<prefix>/Library/bin/mf2005.exe``
on Windows), and puts that directory at the front of ``PATH`` for the run and
its calibration workers, which it logs.

When either of them is missing, the configuration of an enabled section
carries the blocking problem ``MODFLOW runtime is not available.``, with the
installation guidance. This check, like the existence of the MODFLOW input
files, runs even when the validation of the inputs is skipped with ``-s``:
without them the coupled run cannot start.

Layers
------

The layers are listed **from the top down**, and numbered like MODFLOW: layer
``1`` is the top layer. That number is the one every key, message and output
name uses (``river.entries[].layers``, ``wetting.layers``,
``water_table.layer``, ``mfh1``, ``modflow.layers.1.specific_yield``). The
PCRaster MODFLOW extension numbers its layers the other way round, from the
bottom up; RUBEM converts the numbers itself, and the user never writes the
extension's numbers.

The geometry is a model top and one bottom per layer; the top of a layer is
the model top for layer 1 and the bottom of the layer above for the others:

.. code-block:: text

   ------------------------------  model top          top
        layer 1 (top layer)
   ------------------------------  bottom of layer 1  layers[0].bottom
        layer 2
   ------------------------------  bottom of layer 2  layers[1].bottom
        layer 3 (base layer)
   ------------------------------  bottom of layer 3  layers[2].bottom

A section lists at most **9** layers: the name of a per-layer output is its
prefix followed by the layer number and the step (``mfh1`` then the step), so
layer 1 and layer 10 would give the same file names.

On the columns that are active in at least one layer, the top and every bottom
must have a value and each surface must lie strictly below the one above it.
The columns that are inactive in every layer lie outside the groundwater
domain; MODFLOW still needs elevations there, so RUBEM gives them synthetic
layers one metre thick, in memory. The input files are never modified.

The MODFLOW grid has one cell per RUBEM cell, and every MODFLOW cell is a
square whose side is ``GRID.grid`` metres: the row and column widths come from
the grid size of the configuration, whatever the units of the clone. On a
geographic clone this is the square-cell approximation RUBEM already makes for
its own fluxes, not a reprojection.

The configuration section
-------------------------

The section is ``modflow`` in configuration format 1.0 and ``MODFLOW`` in the
legacy format; the keys inside it are the same in both. Every file path is
anchored on the directory of the configuration file when it is relative, like
the other inputs. The section is strict in both formats: a key it does not
know is refused when the configuration is loaded, instead of being ignored.

Lengths are in metres and times in days, the units of the coupling; they are
not configurable.

The example below is a three-layer model with a river on the top layer and
general-head boundaries on the three layers (format 1.0):

.. code-block:: json

   {
     "modflow": {
       "enabled": true,
       "top": "input/modflow/top_model.map",
       "layers": [
         {
           "name": "upper",
           "bottom": "input/modflow/botton3.map",
           "initial_head": "input/modflow/head3.map",
           "boundary": "input/modflow/bound.map",
           "laytype": 1,
           "horizontal_conductivity": {
             "map": "input/modflow/kh_classes3.map",
             "table": "input/modflow/kh3.tbl"
           },
           "vertical_conductivity": "input/modflow/KY3.map",
           "specific_yield": 0.15,
           "specific_storage": 1e-6
         },
         {
           "name": "middle",
           "bottom": "input/modflow/botton2.map",
           "initial_head": "input/modflow/head2.map",
           "boundary": "input/modflow/bound.map",
           "laytype": 2,
           "horizontal_conductivity": {
             "map": "input/modflow/kh_classes2.map",
             "table": "input/modflow/kh2.tbl"
           },
           "vertical_conductivity": "input/modflow/KY2.map",
           "specific_yield": 0.15,
           "specific_storage": 1e-6
         },
         {
           "name": "lower",
           "bottom": "input/modflow/botton.map",
           "initial_head": "input/modflow/head1.map",
           "boundary": "input/modflow/bound.map",
           "laytype": 2,
           "horizontal_conductivity": {
             "map": "input/modflow/kh_classes1.map",
             "table": "input/modflow/kh1.tbl"
           },
           "vertical_conductivity": "input/modflow/KY1.map",
           "specific_yield": 0.15,
           "specific_storage": 1e-6
         }
       ],
       "dis": {"nstp": 5, "tsmult": 1.0, "steady_state": false},
       "solver": {
         "mxiter": 2000,
         "iter1": 20,
         "npcond": 1,
         "hclose": 5.0,
         "rclose": 3.0,
         "relax": 1.0,
         "nbpol": 2,
         "damp": 0.5
       },
       "wetting": {
         "enabled": true,
         "map": "input/modflow/wet.map",
         "layers": [1],
         "wetfct": 1.0,
         "iwetit": 3,
         "ihdwet": 0
       },
       "river": {
         "enabled": true,
         "entries": [
           {
             "layers": [1],
             "stage": "input/modflow/riv_stage.map",
             "bottom": "input/modflow/riv_bot.map",
             "conductance": 0.387,
             "mask": "input/modflow/riv_cond.map"
           }
         ]
       },
       "ghb": {
         "enabled": true,
         "entries": [
           {
             "layers": [1, 2, 3],
             "head": "input/modflow/ghb_head.map",
             "conductance": "input/modflow/ghb_cond.map"
           }
         ]
       },
       "drain": {"enabled": false, "entries": []},
       "coupling": {
         "dynamic_root_depth": {
           "enabled": false,
           "minimum_depth_table": null,
           "water_table": {"method": "highest_active_head", "layer": null}
         }
       },
       "output": {
         "heads": true,
         "river_leakage": true,
         "storage": false,
         "drain_flow": false,
         "root_depth": false
       }
     }
   }

The tables below list every key. A *raster* is a path to a map on the grid of
the clone; where a key accepts a raster or a number, the number is written
without quotes (``0.15`` is a value, ``"0.15"`` is a file name) and stands for
that value in every cell.

Section keys
````````````

.. list-table::
   :header-rows: 1
   :widths: 22 22 12 44

   * - Key
     - Type
     - Unit
     - Description
   * - ``enabled``
     - boolean, default ``false``
     - –
     - Whether the run is coupled to MODFLOW. The other keys are checked only
       when it is ``true``.
   * - ``top``
     - raster, required
     - m
     - Elevation of the model top, the top of layer 1.
   * - ``layers``
     - list of 1 to 9 layers, required
     - –
     - The layers from the top down, see `Layer keys`_.
   * - ``dis``
     - object
     - –
     - Time discretization, see `Time discretization`_.
   * - ``solver``
     - object
     - –
     - PCG solver settings, see `Solver`_.
   * - ``wetting``
     - object
     - –
     - Rewetting of dry cells, see `Wetting`_.
   * - ``river``, ``ghb``, ``drain``
     - objects
     - –
     - The stress packages, see `Rivers, general-head boundaries and drains`_.
       ``river.enabled`` must be ``true``: the river leakage is the baseflow.
   * - ``coupling``
     - object
     - –
     - The root-depth coupling, see `The root-depth coupling`_.
   * - ``output``
     - object
     - –
     - The diagnostics written as rasters, see `Outputs of a coupled run`_.

Layer keys
``````````

.. list-table::
   :header-rows: 1
   :widths: 22 22 12 44

   * - Key
     - Type
     - Unit
     - Description
   * - ``name``
     - text, required
     - –
     - Name of the layer in the messages and logs; unique in the section.
   * - ``bottom``
     - raster, required
     - m
     - Elevation of the bottom of the layer.
   * - ``initial_head``
     - raster, required
     - m
     - Head at the start of the simulation.
   * - ``boundary``
     - raster, required
     - –
     - The MODFLOW ``IBOUND`` array of the layer: ``1`` active, ``0``
       inactive, ``-1`` constant head. A missing value is inactive.
   * - ``laytype``
     - integer, required
     - –
     - BCF layer type. The tens digit is the interblock conductance average
       (``0`` harmonic, ``1`` arithmetic, ``2`` logarithmic, ``3`` arithmetic
       thickness and logarithmic conductivity); the units digit is ``LAYCON``:
       ``0`` confined, ``1`` unconfined (top layer only), ``2`` and ``3``
       convertible. One of ``0``–``3``, ``10``–``13``, ``20``–``23``,
       ``30``–``33``.
   * - ``horizontal_conductivity``
     - raster, positive number, or ``{"map", "table"}``
     - m/day
     - Horizontal hydraulic conductivity. The object form takes a nominal map
       of classes (``map``) and a PCRaster lookup table (``table``) with one
       ``class value`` row per class; the first row that matches a class is
       the one read, as in any PCRaster lookup.
   * - ``vertical_conductivity``
     - raster or positive number
     - m/day
     - Vertical hydraulic conductivity; MODFLOW's vertical leakance between
       layers is computed from it and the layer thicknesses.
   * - ``specific_storage``
     - raster, number ``>= 0`` or ``null``
     - –
     - The confined storage coefficient of the layer, given to BCF as the
       primary storage ``Sf1`` as it is (it is **not** multiplied by the
       layer thickness). Read in transient runs by ``LAYCON`` 0, 2 and 3.
   * - ``specific_yield``
     - raster, number in ``[0, 1]`` or ``null``
     - –
     - Specific yield. Read in transient runs as ``Sf1`` by ``LAYCON`` 1 and
       as the secondary storage ``Sf2`` by ``LAYCON`` 2 and 3.
   * - ``compute_conductivity``
     - boolean, default ``true``
     - –
     - With ``false`` the two conductivity inputs are given to MODFLOW as they
       are, instead of the transmissivity and vertical leakance computed
       from them (the ``COMPUTE`` flag of the extension's
       ``setConductivity``); their units are then those of the MODFLOW arrays
       they replace.

A transient run needs the storage its layer types read: ``specific_storage``
for ``LAYCON`` 0, ``specific_yield`` for ``LAYCON`` 1, both for ``LAYCON`` 2
and 3. A steady-state run reads neither.

Time discretization
```````````````````

.. list-table::
   :header-rows: 1
   :widths: 22 22 12 44

   * - Key
     - Type
     - Unit
     - Description
   * - ``dis.nstp``
     - integer ``>= 1``, default ``1``
     - –
     - Number of MODFLOW time steps in each stress period. With more than
       one, a solver failure before the last of them ends the process instead
       of raising an error; see `Limitations`_.
   * - ``dis.tsmult``
     - number ``> 0``, default ``1.0``
     - –
     - Multiplier of the length of successive time steps.
   * - ``dis.steady_state``
     - boolean, default ``false``
     - –
     - With ``true`` every stress period is steady state: no storage is read
       and the ``storage`` output cannot be enabled.

In a transient run the length of each period is updated to the days of its
month before it runs. The time unit (days) and the length unit (metres) are
fixed.

Solver
``````

The solver is the preconditioned conjugate-gradient package (PCG), the only
one the coupling configures. Its keys are those of ``setPCG`` of the extension:

.. list-table::
   :header-rows: 1
   :widths: 22 22 12 44

   * - Key
     - Type
     - Unit
     - Description
   * - ``solver.mxiter``
     - integer ``>= 1``, default ``2000``
     - –
     - Maximum number of outer iterations.
   * - ``solver.iter1``
     - integer ``>= 1``, default ``20``
     - –
     - Number of inner iterations.
   * - ``solver.npcond``
     - ``1`` or ``2``, default ``1``
     - –
     - Preconditioning: ``1`` modified incomplete Cholesky, ``2``
       polynomial.
   * - ``solver.hclose``
     - number ``> 0``, default ``5.0``
     - m
     - Head change criterion for convergence.
   * - ``solver.rclose``
     - number ``> 0``, default ``3.0``
     - :raw-html:`m<sup>3</sup>day<sup>-1</sup>`
     - Residual criterion for convergence.
   * - ``solver.relax``
     - number ``> 0``, default ``1.0``
     - –
     - Relaxation parameter, used with ``npcond`` 1.
   * - ``solver.nbpol``
     - integer ``>= 0``, default ``2``
     - –
     - Whether the estimate of the upper bound on the maximum eigenvalue is
       2.0 (PCG ``NBPOL``).
   * - ``solver.damp``
     - number ``> 0``, default ``0.5``
     - –
     - Damping factor.

.. note::

   The default criteria, ``hclose`` 5 m and ``rclose`` 3
   :raw-html:`m<sup>3</sup>day<sup>-1</sup>`, are coarse: they are the values
   of the first applications of the coupling and they are kept as defaults,
   not recommended. Tighten them for a study whose heads matter.

The head MODFLOW gives a cell that becomes dry (``HDRY``) is fixed at
``-999.9``.

Wetting
```````

.. list-table::
   :header-rows: 1
   :widths: 22 22 12 44

   * - Key
     - Type
     - Unit
     - Description
   * - ``wetting.enabled``
     - boolean, default ``false``
     - –
     - Whether dry cells may become wet again.
   * - ``wetting.map``
     - raster, required when enabled
     - m
     - The ``WETDRY`` array: its absolute value is the wetting threshold; a
       negative value lets only the cell below a dry cell wet it, a positive
       one also the four horizontal neighbours, and ``0`` never wets the
       cell. A missing value is ``0``.
   * - ``wetting.layers``
     - list of layer numbers, or ``null`` (default)
     - –
     - The layers the map applies to; ``null`` means every layer whose
       ``LAYCON`` is 1 or 3.
   * - ``wetting.wetfct``
     - number ``> 0``, default ``1.0``
     - –
     - Factor of the head a cell takes when it becomes wet.
   * - ``wetting.iwetit``
     - integer ``>= 1``, default ``3``
     - –
     - Wetting is attempted every ``iwetit`` outer iterations.
   * - ``wetting.ihdwet``
     - ``0`` or ``1``, default ``0``
     - –
     - Equation of the head of a cell that becomes wet: ``0``
       :math:`h = BOT + WETFCT (h_n - BOT)`, ``1``
       :math:`h = BOT + WETFCT \cdot THRESH`.

MODFLOW-2005 reads ``WETDRY`` only for layers whose ``LAYCON`` is 1 or 3, so
every listed layer must have one of those types: a model whose lower layers
are ``LAYCON`` 2 needs ``laytype`` 3 on them to be rewetted.

Rivers, general-head boundaries and drains
``````````````````````````````````````````

Each package has ``enabled`` (default ``false``) and a list of ``entries``;
an enabled package needs at least one entry. An entry applies the same maps
to every layer of its ``layers`` list, and a layer may appear in at most one
entry of a package. The stress data are read and given to MODFLOW once, when
the run starts, and hold for every stress period.

A cell of an entry, in a listed layer, is a cell with a positive conductance
(inside the ``mask`` for a river) that is active in that layer (``boundary``
not ``0``); the conductance is zero everywhere else.

.. list-table::
   :header-rows: 1
   :widths: 22 22 12 44

   * - Key
     - Type
     - Unit
     - Description
   * - ``river.entries[].layers``
     - list of layer numbers
     - –
     - The layers the river cells belong to.
   * - ``river.entries[].stage``
     - raster
     - m
     - River stage.
   * - ``river.entries[].bottom``
     - raster
     - m
     - Elevation of the riverbed bottom.
   * - ``river.entries[].conductance``
     - raster or positive number
     - :raw-html:`m<sup>2</sup>day<sup>-1</sup>`
     - Riverbed conductance of each river cell. A number needs ``mask``.
   * - ``river.entries[].mask``
     - raster, optional
     - –
     - The river cells: the cells where it is positive. With a conductance
       raster, it restricts the river to those cells.
   * - ``ghb.entries[].layers``
     - list of layer numbers
     - –
     - The layers of the boundary.
   * - ``ghb.entries[].head``
     - raster
     - m
     - Head of the external source.
   * - ``ghb.entries[].conductance``
     - raster
     - :raw-html:`m<sup>2</sup>day<sup>-1</sup>`
     - Boundary conductance.
   * - ``drain.entries[].layers``
     - list of layer numbers
     - –
     - The layers of the drains.
   * - ``drain.entries[].elevation``
     - raster
     - m
     - Drain elevation.
   * - ``drain.entries[].conductance``
     - raster
     - :raw-html:`m<sup>2</sup>day<sup>-1</sup>`
     - Drain conductance.

.. warning::

   MODFLOW defines a boundary cell by its layer, row and column, so an entry
   listing several layers creates one boundary cell per layer, each with the
   full conductance of the map. A general-head boundary on the three layers
   of a column therefore has **three times** the conductance of the map
   between the aquifer and its source. Divide the conductance map by the
   number of layers when the map holds the conductance of the whole column.

A river whose cells lie at different depths can be split into several entries,
each with its own ``mask`` and layer.

The root-depth coupling
```````````````````````

.. list-table::
   :header-rows: 1
   :widths: 22 22 12 44

   * - Key
     - Type
     - Unit
     - Description
   * - ``coupling.dynamic_root_depth.enabled``
     - boolean, default ``false``
     - –
     - Whether the water table restricts the roots of the vegetation, see
       `Roots and the water table`_.
   * - ``coupling.dynamic_root_depth.minimum_depth_table``
     - lookup table, required when enabled
     - cm
     - Minimum root depth of each soil class (the classes of
       ``RASTERS.soil``), in the units of the rootzone depth table.
   * - ``coupling.dynamic_root_depth.water_table.method``
     - ``"highest_unconfined"`` (default), ``"highest_active_head"`` or
       ``"layer"``
     - –
     - Which head is the water table, cell by cell.
   * - ``coupling.dynamic_root_depth.water_table.layer``
     - layer number, only with ``"layer"``
     - –
     - The layer whose head is the water table.

The three methods read the heads of the step, leaving out the cells that are
dry or inactive in their layer:

- ``highest_active_head`` takes the first head from the top down;
- ``highest_unconfined`` does the same over the layers whose ``LAYCON`` is 1,
  2 or 3, and skips a convertible layer (``LAYCON`` 2 or 3) where its head is
  above the top of the layer, that is, where the layer is confined; it needs a
  layer of one of those types;
- ``layer`` takes the head of ``water_table.layer``.

Output keys
```````````

.. list-table::
   :header-rows: 1
   :widths: 22 22 12 44

   * - Key
     - Type
     - Unit
     - Description
   * - ``output.heads``
     - boolean, default ``true``
     - –
     - Head of every layer.
   * - ``output.river_leakage``
     - boolean, default ``true``
     - –
     - River exchange, in both directions and net.
   * - ``output.storage``
     - boolean, default ``false``
     - –
     - Storage flow of every layer; transient runs only.
   * - ``output.drain_flow``
     - boolean, default ``false``
     - –
     - Drain flow of every drain layer.
   * - ``output.root_depth``
     - boolean, default ``false``
     - –
     - The water table and root depth of the root-depth coupling; written
       only when that coupling is enabled.

Rules the configuration and the inputs must follow
--------------------------------------------------

When the configuration is loaded
````````````````````````````````

An enabled section is refused when it breaks one of these rules; every
violation is listed in one message:

- ``top`` and at least one layer are given, at most 9 layers, and the layer
  names are unique;
- ``LAYCON`` 1 appears only on layer 1, as MODFLOW-2005 requires;
- ``river.enabled`` is ``true``, every enabled package has an entry, every
  layer number is a layer of the section and appears at most once per
  package, and a numeric river conductance comes with a ``mask``;
- a transient run gives the storage each layer type reads (see
  `Layer keys`_), and a steady-state run does not ask for the ``storage``
  output;
- enabled wetting gives ``map``, and each of its layers has ``LAYCON`` 1 or 3
  (with ``layers`` ``null``, at least one layer has);
- an enabled root-depth coupling gives ``minimum_depth_table``;
  ``water_table.layer`` is given with the ``layer`` method, and only with it.

Before every coupled run
````````````````````````

Always, even with ``-s``, and blocking: every file the coupled run reads
exists and is not empty (the files of a disabled package, of disabled wetting
and of a disabled root-depth coupling are not read, so not checked), and the
MODFLOW runtime is available (see `Requirements`_).

With the validation of the inputs, which ``-s`` skips, the content is checked.
Blocking:

- a raster that cannot be read or does not share the geometry of the clone;
- a boundary value other than ``-1``, ``0`` and ``1``;
- the model top or a bottom missing on a column active in any layer, or a
  bottom not strictly below the top of its layer there (the message names the
  layer and the first row and column);
- an initial head, conductivity or (in a transient run) storage raster
  missing on an active cell of its layer;
- an initial head below the layer bottom in every active cell of the layer;
- an initial head equal to a MODFLOW no-data marker (``-888``, ``-999``,
  ``-999.9``, ``-999.99`` or ``-9999``) in an active cell: the extension
  would read it as a head, start the cell dry and carry the value into the
  head outputs, so give the cell a head or make it inactive;
- a conductivity class map in PCRaster format that is not nominal, or a
  class on an active cell that the lookup table does not give a positive
  value;
- an enabled package layer without any cell (the extension would end the
  process on it), or a stage, bottom, head or elevation missing on a cell of
  the package;
- with the root-depth coupling, a minimum root depth table that does not
  cover the soil classes, or a value that is not in
  :math:`(0, Z_r]`, :math:`Z_r` being the rootzone depth of the class.

Non-blocking warnings:

- an initial head below the layer bottom in some active cells (the count is
  given): MODFLOW starts with those cells dry;
- river cells whose riverbed bottom lies outside the elevation interval of
  their layer, reported as ``N of M river cells of layer k have their bed
  outside the layer's elevation interval``, with how many are below the
  layer bottom and how many above the layer top. Moving them to another
  layer, with a second river entry, is a modelling decision the run does
  not take.

Outputs of a coupled run
------------------------

The diagnostics are raster series, one map per step, written in the raster
formats of the run (``RASTER_FILE_FORMAT``) with the naming of the other
output variables (``mfh10000.001`` in PCRaster format, ``mfh1000001.tif`` in
GeoTIFF for the head of layer 1 at step 1). They are selected by the
``output`` keys of the section, not by ``GENERATE_FILE``, and no time series
is written for them, so a run that enables no raster format writes none of
them.

.. list-table::
   :header-rows: 1
   :widths: 18 22 14 46

   * - Prefix
     - Written when
     - Unit
     - Content
   * - ``mfh<n>``
     - ``output.heads``
     - m
     - Head of layer ``n``. Dry cells have no value.
   * - ``mfaq2rv``
     - ``output.river_leakage``
     - :raw-html:`m<sup>3</sup>day<sup>-1</sup>`
     - Leakage from the aquifer to the river, summed over the river layers;
       ``bfw`` is this flux as a depth.
   * - ``mfrv2aq``
     - ``output.river_leakage``
     - :raw-html:`m<sup>3</sup>day<sup>-1</sup>`
     - Leakage from the river to the aquifer.
   * - ``mfrvnet``
     - ``output.river_leakage``
     - :raw-html:`m<sup>3</sup>day<sup>-1</sup>`
     - Net river leakage, positive into the aquifer.
   * - ``mfst<n>``
     - ``output.storage`` (transient)
     - :raw-html:`m<sup>3</sup>day<sup>-1</sup>`
     - Storage flow of layer ``n``.
   * - ``mfdrn<n>``
     - ``output.drain_flow``
     - :raw-html:`m<sup>3</sup>day<sup>-1</sup>`
     - Drain flow of layer ``n``, negative out of the aquifer; one series per
       layer of the drain entries.
   * - ``mfwt``
     - ``output.root_depth`` and the root-depth coupling
     - m
     - Water-table head of the step, the one the next step's roots see.
   * - ``mfgwd``
     - ``output.root_depth`` and the root-depth coupling
     - cm
     - Depth of the previous step's water table below the terrain; no value
       at step 1.
   * - ``mfzr``
     - ``output.root_depth`` and the root-depth coupling
     - cm
     - Effective root depth of the vegetation.
   * - ``mfzfrac``
     - ``output.root_depth`` and the root-depth coupling
     - –
     - Effective root depth as a fraction of the rootzone depth.

The ``bfw`` output variable, its raster series and its time series, carries
the baseflow of the coupling, the aquifer-to-river leakage in millimetres per
step (see `Baseflow`_).

The run directory
-----------------

MODFLOW writes its input and result files (``pcrmf.*``, ``fort.*``) into
``<output directory>/modflow``, which the run creates when it starts and
removes after the last step. The run owns that directory: it refuses to start
when the directory already exists, so that it never removes files it did not
write, and removes it again when MODFLOW cannot start.

A run that fails during the simulation keeps the directory, with the MODFLOW
listing file ``pcrmf.lst``, for inspection; move or remove it before running
into the same output directory again.

In a calibration each evaluation runs in its own temporary output directory
under ``--temp-dir``, so its MODFLOW directory, and the conductivity tables of
its candidate, are removed with it.

Roots and the water table
-------------------------

.. warning::

   The root-depth coupling is experimental and off by default. It changes the
   evapotranspiration of the vegetated area.

With ``coupling.dynamic_root_depth.enabled``, the water table of a step
restricts the roots of the vegetation at the next step. The depth of the water
table is measured from the terrain, the DEM of the configuration
(``RASTERS.dem``), not from the model top:

.. math::
   :label: groundwater-depth
   :nowrap:

    \[D_{GW} = \max\left(100 \left(z_{DEM} - h_{WT}\right),\ 0\right)\]

.. math::
   :label: groundwater-root-depth
   :nowrap:

    \[Z_{r,eff} = \min\left(Z_r,\ \max\left(Z_{r,min},\ D_{GW}\right)\right), \quad f_r = \frac{Z_{r,eff}}{Z_r}\]

where:

- :math:`D_{GW}` – depth of the water table below the terrain [cm];
- :math:`z_{DEM}` – terrain elevation [m];
- :math:`h_{WT}` – water-table head of the previous step [m], chosen by
  ``water_table.method``;
- :math:`Z_r` – rootzone depth of the soil class [cm];
- :math:`Z_{r,min}` – minimum root depth of the soil class, from
  ``minimum_depth_table`` [cm];
- :math:`Z_{r,eff}` – effective root depth [cm];
- :math:`f_r` – fraction of the rootzone the roots reach [-].

At the first step, and wherever the previous water table has no value, the
roots reach the whole rootzone (:math:`f_r = 1`). The water stress coefficient
of the vegetated area is then computed on the soil moisture, the wilting point
and the field capacity of the rootzone multiplied by :math:`f_r`; the bare
soil keeps the coefficient of the whole rootzone, and the soil water balance
itself is not changed.

Calibrating a coupled model
---------------------------

``rubem calibrate`` runs the coupled model at every evaluation whenever the
configuration enables MODFLOW; no option is needed. The storage of the layers,
the conductivity of the classes of a lookup table and the numeric river
conductances can join the search, by name, when ``--bound`` or ``--fix`` names
them. :ref:`calibration:MODFLOW parameters` lists the names and the rules.

Limitations
-----------

- **Solver failures.** A stress period that does not converge raises an error
  that names the period and the listing file, and the run stops, keeping its
  run directory; in a calibration the evaluation fails and is ranked behind
  every other. That holds when the solver fails at the last time step of the
  period, which is always the case with the default ``dis.nstp`` of 1. With
  more time steps, a failure at an earlier one stops MODFLOW before it writes
  the heads of the period, and the PCRaster MODFLOW extension then ends the
  whole process (``Can not open head value result file``) instead of
  returning an error; the run directory, with ``pcrmf.lst``, is kept. In a
  calibration that ends the worker process, and with it the calibration,
  which is why ``rubem calibrate`` warns when ``dis.nstp`` is above 1.
- The MODFLOW packages are DIS, BAS, BCF, RCH, RIV, GHB, DRN and the PCG
  solver, and no other: no well package (WEL), no other flow package or
  solver.
- The stress packages (RIV, GHB, DRN) are static: their maps are read once and
  hold for the whole simulation.
- Days and metres only; square cells of side ``GRID.grid``.
- At most 9 layers.
- The MODFLOW diagnostics are raster series only: no time series of them is
  written, and the evaluations of a calibration, which write no raster, do not
  write them either. Their seven-character prefixes (``mfaq2rv``,
  ``mfrv2aq``, ``mfrvnet``, ``mfzfrac``) leave room for 999 steps in GeoTIFF
  names and 9,999 in PCRaster names.
- The conductance of a general-head boundary, a drain or a river entry that
  lists several layers is given to each of them, so it adds up across the
  layers (see the warning under
  `Rivers, general-head boundaries and drains`_).
- Wetting applies one ``WETDRY`` map to its layers, which must be ``LAYCON`` 1
  or 3.
- The river-to-aquifer leakage adds water to the aquifer that no RUBEM flux
  loses.

References
----------

- PCRaster MODFLOW extension, version 4.4.2:
  `overview <https://pcraster.geo.uu.nl/pcraster/4.4.2/documentation/modflow/index.html>`__,
  `layer numbering (DIS) <https://pcraster.geo.uu.nl/pcraster/4.4.2/documentation/modflow/dis.html>`__,
  `BCF <https://pcraster.geo.uu.nl/pcraster/4.4.2/documentation/modflow/bcf.html>`__,
  `RIV <https://pcraster.geo.uu.nl/pcraster/4.4.2/documentation/modflow/riv.html>`__,
  `RCH <https://pcraster.geo.uu.nl/pcraster/4.4.2/documentation/modflow/rch.html>`__,
  `GHB <https://pcraster.geo.uu.nl/pcraster/4.4.2/documentation/modflow/ghb.html>`__,
  `DRN <https://pcraster.geo.uu.nl/pcraster/4.4.2/documentation/modflow/drn.html>`__,
  `solvers <https://pcraster.geo.uu.nl/pcraster/4.4.2/documentation/modflow/solver.html>`__.
- Online guide to MODFLOW-2005:
  `index <https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/index.html>`__,
  `BCF <https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/bcf.html>`__,
  `RIV <https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/riv.html>`__,
  `GHB <https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/ghb.html>`__,
  `DRN <https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/drn.html>`__,
  `PCG <https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/pcg.html>`__.

.. [HARBAUGH2005] Harbaugh, A.W. (2005). MODFLOW-2005, the U.S. Geological
   Survey modular ground-water model — the Ground-Water Flow Process. U.S.
   Geological Survey Techniques and Methods 6-A16.
   https://pubs.usgs.gov/tm/2005/tm6A16/

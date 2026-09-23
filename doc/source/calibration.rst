Calibration
===========

.. role:: raw-html(raw)
   :format: html

The ``rubem calibrate`` command fits the calibration parameters of the model to
an observed streamflow series with a differential evolution search
[STORN1997]_. Every candidate the search proposes is a complete simulation:
the command builds the configuration of the candidate, runs it, samples the
resulting time series at the stations and scores it against the observations.

The options of the command are listed in the user guide, under
:ref:`userguide:Running RUBEM`. This page documents what happens between them:
the objective, the parameters and their bounds, the settings of the search and
how to budget a run, the inputs it needs, what it writes, what it reports while
it runs, and how it uses the machine it runs on.

What the calibration fits
-------------------------

The model has nine calibration parameters, the ``CALIBRATION`` section of the
configuration file: :math:`\alpha`, :math:`b`, :math:`w_1`, :math:`w_2`,
:math:`w_3`, :math:`RCD`, :math:`f`, :math:`\alpha_{GW}` and :math:`x`. They
are described in :ref:`overview:Calibration and Validation`. The search covers
at most eight of them; the slope factor weight :math:`w_3` is not searched but
derived from the other two weights, because the three weights of the potential
runoff coefficient must add up to 1, and ``--fix`` takes further parameters out
of the search for one run.

The observations are a streamflow series at the sample stations of the
configuration, one column per station. By default the simulated counterpart is
``arn``, the accumulated total runoff, in
:raw-html:`m<sup>3</sup>s<sup>-1</sup>`, which is the variable an observed
streamflow record is directly comparable with. ``--variable`` selects another
output variable, one of ``itp``, ``bfw``, ``srn``, ``eta``, ``lfw``, ``rec``,
``smc``, ``rnf`` and ``arn``; note that ``rnf`` is the total runoff of a single
cell, in millimeters, not a discharge, so an observed series compared with it
must be in the same quantity.

Each evaluation runs the whole simulation period of the configuration. The
calibration never changes the period, the inputs or the aggregation: of what
the results depend on, it changes the nine parameters and nothing else, apart
from the parameters of the groundwater model a calibration of a coupled
configuration names, see `MODFLOW parameters`_.

The objective function
----------------------

The efficiency
``````````````

The agreement between a simulated and an observed series at one station is the
Nash-Sutcliffe efficiency [MCCUEN2006]_:

.. math::
   :label: calibration-nse
   :nowrap:

    \[NSE = 1 - \frac{\sum_{t}{\left(Q_{sim,t} - Q_{obs,t}\right)^2}}{\sum_{t}{\left(Q_{obs,t} - \overline{Q_{obs}}\right)^2}}\]

where:

- :math:`Q_{sim,t}` – simulated value of the station at time step :math:`t`;
- :math:`Q_{obs,t}` – observed value of the station at time step :math:`t`;
- :math:`\overline{Q_{obs}}` – mean of the observed values used in the sum.

Both sums run over the same pairs, and the mean is the mean of the observed
values of those pairs: a step dropped because the simulation has no value for
it is dropped from the mean as well, so numerator and denominator always
describe the same sample.

Which values count
``````````````````

A pair counts only when both of its members count. A value does not count when
it is not finite (``NaN`` and the infinities), when it is **negative**, or when
it is at or above ``1e30``.

Every quantity the two series carry is a flux or a storage and cannot be
negative, so a negative entry is not a measurement but a gap: the ``-9999`` the
model and the usual observation tables write, the ``-1`` some gauge records
use, or any other negative marker of their own. All of them are dropped alike,
and nothing has to be declared for it. Zero is a value and not a gap: a station
may well record no flow.

The ``1e30`` threshold is how the PCRaster missing value ``1e31`` is masked.
The value does not round-trip exactly through ``Float32`` — written and read
back it becomes ``9.999999...e30`` — so the mask rejects everything at or above
``1e30`` instead of comparing with the constant. No streamflow or runoff of a
real basin comes anywhere near that magnitude. An empty cell, or a cell that is
not a number at all, is read as ``NaN`` and masked the same way.

How many observed values the mask dropped is reported per station before the
search starts, on the terminal and in the ``dropped`` column of
:file:`observed.csv`, so that a gauge that is nearly empty over the simulated
window is seen before the model runs and not after them.

Stations and the average
````````````````````````

The two series are aligned on the station ids they share and on the time steps
they share; a station or a step present on one side only is ignored.

A station has no efficiency when fewer than two of its pairs count, or when all
of its valid observations are equal: a constant record has no variability
for the efficiency to explain and would divide by zero. Such a station is
reported as having no efficiency and is left out of the average, instead of
dragging it.

The efficiency of a candidate is the mean over the **selected** stations that
do have one. Without ``--stations`` every shared station is selected.
``--stations 1,2,3`` names the ids the mean is taken over, and the stations it
leaves out are still sampled, still compared and still measured: they carry
``false`` in the ``in_selection`` column of :file:`observed.csv` and of
:file:`stations.csv`, and their goodness of fit is recorded by every
evaluation. That is the calibration and validation split — the search is
driven by some of the gauges, and the others say what the parameters it found
do at a gauge that had no say in them.

A selection that names none of the comparable stations is refused before the
search starts, since every evaluation would fail on it; a selection that names
some unknown id keeps the ids that exist and reports the others once.

A mismatch between the observations and the configuration is not a poor
candidate, and the two kinds of it that can be told before any model run are
refused before the search starts: an observed series with no time step in
common with the simulated steps that survive the spin-up, and one whose station
ids match none of the ids of the sample locations raster (an observed station
the configuration does not sample is reported once and ignored). With the
``zones`` aggregation the station ids are only known once a run has written
:file:`zones_mapping.csv`, so that check, and the check of the selected
stations, are made against the observed series alone.

What cannot be told in advance surfaces inside the evaluations: a series whose
shared stations all lack an efficiency, because every observation is missing or
constant, fails each evaluation after its simulation has run. The evaluation is
then recorded with the message of the error in its ``error`` column and with
the objective ``1e30``, like any other failure, and the search carries on; the
calibration ends with an error only once no evaluation of the whole run has
succeeded.

.. warning::

   Such a failure is paid for in model runs before it is reported. The
   per-generation log line is the early sign: a best objective of ``1e+30`` from
   the first generation on means that every candidate failed. Check the observed
   file against a run of the configuration first, over a few time steps, as
   `Running on a cluster or a large machine`_ describes.

The spin-up window
``````````````````

``--spinup-steps`` excludes the leading time steps of the simulation from the
comparison: every step whose number is at most ``--spinup-steps`` is dropped
from both series before they are aligned. The simulation still runs from its
first step — the point is to let the storages of the model fill before their
effect is scored, not to shorten the run.

From the efficiency to the objective
````````````````````````````````````

The differential evolution minimizes, so the efficiency is turned into a cost:

.. math::
   :label: calibration-objective
   :nowrap:

    \[FO = 1000 \cdot \left(100 \cdot \left(1 - NSE\right)\right)^2\]

A perfect simulation, :math:`NSE = 1`, gives :math:`FO = 0`; a simulation no
better than the mean of the observations, :math:`NSE = 0`, gives
:math:`FO = 10^7`; and the cost grows quadratically as the efficiency falls
further.

A candidate that is never run — one the admissibility check rejects — and a
candidate whose run or evaluation fails are both recorded with the objective
``1e30``. The worst value a real run can produce is far below it (an efficiency
of :math:`-100`, already an absurd simulation, gives about
:math:`1.0 \times 10^{11}`), so a rejected or failed candidate always ranks
behind every candidate that was actually evaluated. The value is finite on
purpose: it sorts, it is written to JSON, and it appears in the table of
evaluations like any other objective.

Free parameters and their bounds
--------------------------------

The eight searched parameters, in the order of the decision vector, with the
bounds the application settings declare (:file:`rubem/appsettings.json`,
section ``value_ranges.variables``). These are the same ranges the
configuration loader validates against, so any candidate inside the bounds is a
configuration the model accepts.

.. list-table:: Searched parameters
   :header-rows: 1
   :widths: 20 20 40 20

   * - Configuration key
     - Symbol
     - Description
     - Bounds
   * - ``alpha``
     - :math:`\alpha`
     - Interception parameter
     - :math:`0.01 \leq \alpha \leq 10`
   * - ``b``
     - :math:`b`
     - Rainfall intensity coefficient
     - :math:`0.01 \leq b \leq 1`
   * - ``w_1``
     - :math:`w_1`
     - Land use factor weight
     - :math:`0 \leq w_1 \leq 1`
   * - ``w_2``
     - :math:`w_2`
     - Soil factor weight
     - :math:`0 \leq w_2 \leq 1`
   * - ``rcd``
     - :math:`RCD`
     - Regional consecutive dryness level
     - :math:`1 \leq RCD \leq 10`
   * - ``f``
     - :math:`f`
     - Flow direction factor
     - :math:`0.01 \leq f \leq 1`
   * - ``alpha_gw``
     - :math:`\alpha_{GW}`
     - Baseflow recession coefficient
     - :math:`0.01 \leq \alpha_{GW} \leq 1`
   * - ``x``
     - :math:`x`
     - Flow recession coefficient
     - :math:`0 \leq x \leq 1`

.. note::

   The configuration file writes the rainfall intensity coefficient as ``b``,
   and so does the calibrated configuration the run writes;
   :file:`evaluations.csv` and :file:`result.json` spell it ``beta``, which is
   the name the parameter carries inside the package. They are the same
   parameter. ``--bound`` and ``--fix`` accept either spelling, as they accept
   ``w1`` and ``w2`` for ``w_1`` and ``w_2``.

The ninth parameter is derived rather than searched:

.. math::
   :label: calibration-w3
   :nowrap:

    \[w_3 = 1 - \left(w_1 + w_2\right)\]

so a search over both weights is under the linear constraint
:math:`w_1 + w_2 \leq 1`. The constraint is handed to the optimizer, which
checks it before the objective and never spends a model run on a candidate
whose slope factor weight would come out negative. The derived weight must also
lie inside its own range, :math:`0 \leq w_3 \leq 1`; a candidate for which it
does not is rejected without a run and recorded with the error
``inadmissible``. Both checks are guards rather than a part of the search: the
optimizer keeps its trial vectors inside the bounds and drops the ones that
violate the constraint, so it does not propose an inadmissible candidate of its
own.

Narrowing a range for one run
`````````````````````````````

``--bound NAME=MIN:MAX``, repeatable, searches one parameter in a range of the
caller's choosing instead of the range of the application settings:

.. code-block:: console

   $ rubem calibrate -c project-config.json --observed observed.csv -o calibration \
       --bound alpha=1:10 --bound w_1=0.1:1 --bound rcd=1:5

A bound may only **narrow** the settings range, never widen it: its minimum
must lie at or above the minimum of the settings, its maximum at or below their
maximum, and the minimum below the maximum. Anything else is refused before the
search starts, because a candidate outside the settings range is a
configuration the loader would reject anyway. Bounding the derived ``w_3`` is
refused as well: bound ``w_1`` and ``w_2`` instead. So is bounding a parameter
that is fixed, which has no range left to search.

Narrowing is what a known basin buys: the ranges of the settings are the ones
the model accepts at all, and a range that past work has already narrowed
concentrates the population where the answer is instead of spending members on
values that were never plausible.

Keeping a parameter out of the search
`````````````````````````````````````

``--fix NAME=VALUE``, repeatable, pins a parameter for the whole run:

.. code-block:: console

   $ rubem calibrate -c project-config.json --observed observed.csv -o calibration --fix x=0

The coordinate **leaves the decision vector**: the search loses one dimension,
the optimizer never moves the parameter, and the population is no longer spent
exploring it. The pinned value is nonetheless one of the nine parameters every
candidate is run with, and it is in the best parameters, in the calibrated
configuration and under ``settings.fixed`` in :file:`result.json`.

A fixed value must lie inside the range of the application settings, and at
least one parameter must be left free; both are checked before the search
starts. The fixed parameters, and any range a ``--bound`` narrowed, are logged
by the ``rubem.calibration`` logger when the run starts, so a logging
configuration that shows informational records replays exactly what was
searched.

The two weights are the case where fixing changes more than the dimension:

- **Both weights searched**: the pair is kept under the linear constraint
  :math:`w_1 + w_2 \leq 1`.
- **One weight fixed**: there is no pair left to constrain, so the constraint
  becomes a bound on the weight that is still free — its maximum drops to
  :math:`1 - w_{fixed} - w_{3,min}`, which is what keeps the derived
  :math:`w_3` inside its own range. If that leaves the free weight a single
  value (``--fix w_1=1`` leaves :math:`w_2 = 0`), that weight is fixed at it
  as well and leaves the decision vector, so the dimension and the budget
  describe the search that runs; if it leaves no value at all, the run is
  refused instead of searching an empty range.
- **Both weights fixed**: :math:`w_3` is a single number. It is derived once
  and checked before the search; a pair that does not add up to a valid third
  weight is refused.

The starting point of the search, ``x0``, is the parameter set of the
configuration being calibrated. The optimizer places it in the initial
population, so the configuration's own parameters are always among the
candidates of the first generation and a calibration can never return something
worse than what it started from without the table showing why. A coordinate of
that starting point which a narrowed bound excludes is moved onto the bound it
crosses, and the move is logged: the run starts from the admissible point
closest to the configuration rather than ending before its first evaluation.

MODFLOW parameters
------------------

A configuration that enables the :doc:`MODFLOW coupling </groundwater>` is
calibrated like any other: no option is needed, and every evaluation runs the
coupled model. Its section also offers parameters of the groundwater model to
the search. They are named after where they live in the section, with the
layers numbered from the top down, as in the configuration:

.. list-table:: MODFLOW parameters
   :header-rows: 1
   :widths: 34 36 12 18

   * - Name
     - Parameter
     - Unit
     - Values it may take
   * - ``modflow.layers.<n>.specific_yield``
     - Specific yield of layer ``n``
     - –
     - :math:`(0, 1]`
   * - ``modflow.layers.<n>.specific_storage``
     - Confined storage coefficient of layer ``n``
     - –
     - :math:`(0, \infty)`
   * - ``modflow.layers.<n>.kh.<class>``
     - Horizontal conductivity of one class of the lookup table of layer ``n``
     - m/day
     - :math:`(0, \infty)`
   * - ``modflow.river.<i>.conductance``
     - Conductance of every river cell of river entry ``i``, counted from 1
     - :raw-html:`m<sup>2</sup>day<sup>-1</sup>`
     - :math:`(0, \infty)`

A name exists only where the configuration gives a number that the run reads;
a raster is not a number to search:

- the storage of a layer, when the section gives it as a number, the run is
  transient and the layer type reads it: ``LAYCON`` 0 reads the specific
  storage, ``LAYCON`` 1 the specific yield, ``LAYCON`` 2 and 3 both;
- the conductivity of a class, when the horizontal conductivity of the layer
  is a class ``map`` with a lookup ``table``: one name per class of the
  table, spelt as a number in its shortest form (``01`` and ``1.0`` are class
  ``1``). Only the row PCRaster reads for a class is named: an interval row
  is not, nor a row whose class an earlier row, numeric or interval, already
  matches;
- the conductance of a river entry, when it is a number (with its ``mask``).

A MODFLOW parameter is **never searched by default**. It joins the search only
when ``--bound`` names it, and the bound is mandatory, since the application
settings have no range for it: it must be finite, its minimum below its
maximum, and both inside the values the parameter may take. ``--fix`` pins
one at a value inside the same values instead, and naming a parameter in both
is refused. A name that is not a MODFLOW parameter of the configuration is
refused with the list of the ones it offers, and a MODFLOW name given for a
configuration that does not enable MODFLOW is refused as well; all of that
before the search starts.

.. code-block:: console

   $ rubem calibrate -c project-config.json --observed observed.csv -o calibration \
       --bound modflow.layers.1.specific_yield=0.05:0.3 \
       --bound modflow.layers.1.kh.2=0.05:0.5 --fix alpha_gw=0.5

The searched MODFLOW parameters follow the eight parameters of the model in the
decision vector, so each of them is one more dimension in
`The evaluation budget`_, and a search may leave every parameter of the model
fixed and search MODFLOW parameters only. The starting point takes their
values from the configuration, moved onto the bound like the others.

Every candidate carries its MODFLOW values into the configuration of its
evaluation: the numbers replace the ones of the section, and the classes of a
lookup table are written, with the other rows of the table unchanged, into
:file:`kh_layer<n>.tbl` in the temporary directory of the evaluation, which the
layer then reads; the configured table is never modified. The parameters that
were searched or fixed appear in :file:`evaluations.csv`, in
:file:`result.json` and in the calibrated configuration, see
`Artifacts of a run`_.

.. note::

   In a coupled run the baseflow comes from MODFLOW, and the recession
   coefficient :math:`\alpha_{GW}` has no effect on the simulation (see
   :ref:`groundwater:The saturated zone`). Fix it, as in the example above,
   so that the search does not spend a dimension on it.

.. warning::

   With ``dis.nstp`` above 1, a candidate whose MODFLOW solver fails before
   the last time step of a stress period ends its worker process, and with it
   the calibration, instead of being recorded as a failed evaluation; see
   :ref:`groundwater:Limitations`. With ``dis.nstp`` 1 such a candidate is a
   failed evaluation like any other.

The search
----------

Settings
````````

The search is SciPy's ``differential_evolution``. Three of the settings that
decide how it moves are on the command line, because a run may have to
reproduce the settings of an earlier calibration; the budget, ``--maxiter`` and
``--popsize``, is `The evaluation budget`_ and ``--seed`` is below; the rest
describe the method and are fixed.

``--strategy`` (default ``best1exp``)
   How a trial vector is built. With the default, it comes from the best member
   of the population plus a scaled difference of two random members, with
   exponential crossover. A best-based strategy exploits the best candidate
   found so far and converges in fewer generations than the random-base ones
   [STORN1997]_, at some cost in exploration, which the dithered mutation below
   offsets. Fewer generations is what matters when one evaluation is a full
   simulation. Every strategy name SciPy accepts is accepted here.

``--init`` (default ``sobol``)
   The initial population: ``sobol``, ``latinhypercube``, ``halton`` or
   ``random``. The default is a Sobol' sequence over the bounds, which covers
   the box far more evenly than a random sample, so the initial evaluations are
   not wasted on clusters and gaps. It is also the one initialization that
   resizes the population — see `The evaluation budget`_.

``--polish`` / ``--no-polish`` (default ``--no-polish``)
   Whether the best candidate is refined by a local search once the last
   generation is over; see `Polishing`_.

``mutation=(0.5, 1.0)``
   A pair, not a number: the mutation constant is drawn anew for every
   generation between the two values (*dithering*). It widens the range of step
   sizes the search takes without any tuning and reduces the chance of
   stagnating in a local optimum.

``recombination=0.7``
   The probability with which a trial vector keeps a component of the mutant
   rather than of its parent. A high value suits parameters that interact, as
   the three weights and the runoff coefficients do.

``updating="deferred"``
   The whole generation is evaluated before the population is updated. This is
   what makes the generation a batch that can be spread over the worker
   processes; the immediate alternative is inherently serial.

``--seed`` seeds the random generator of the search: the same seed gives the
same initial population and the same random draws of the mutation and of the
crossover. That alone does not make two calibrations comparable candidate by
candidate, because from the first generation on the selection reads the
objectives, so the candidates a run proposes depend on the values the
simulations returned. Two runs follow the same path only when the simulation
itself is reproducible — see `A fixed drainage network`_.

Polishing
`````````

Polishing is **off by default**, and on request with ``--polish``. When it is
on, the best candidate of the last generation is handed to a local search
(L-BFGS-B, or trust-constr when both weights are searched and the linear
constraint is therefore present), which keeps the result only if it improves
the objective.

The reason not to pay for it by default is the price of a gradient here. The
local search has no derivatives to work from, so it estimates them by finite
differences: one model run per free parameter, plus the point itself, for every
step it takes, and those runs are made one at a time, outside the batch a
generation is spread over. On the full search one such step is nine serial
simulations, where a generation is 128 parallel ones. What it estimates is a gradient of an
objective read back from a simulated table, which the model does not provide
reliably at that scale. The evaluations polishing makes are recorded like any
other, so they appear in :file:`evaluations.csv` and in ``nfev``.

The evaluation budget
`````````````````````

The number of population members is not ``--popsize``: it is

.. math::
   :label: calibration-members
   :nowrap:

    \[members = \max\left(5,\ popsize \times N\right)\]

with :math:`N` the number of free parameters — eight, minus one for every
``--fix``, plus one for every bounded parameter of `MODFLOW parameters`_. With
``--init sobol``, the default, that count is then rounded up to the next power
of two, because a Sobol' sequence is balanced only over a
power-of-two sample; the other three initializations use it as it is. Every
generation evaluates one candidate per member, and the initial population is
one more round of evaluations on top of ``--maxiter`` generations, so

.. math::
   :label: calibration-runs
   :nowrap:

    \[runs \leq members \times \left(maxiter + 1\right)\]

With the defaults and no fixed parameter, ``--popsize 15`` gives
:math:`15 \times 8 = 120`, rounded up to **128 members**, and ``--maxiter 100``
gives at most :math:`128 \times 101 = 12\,928` model runs. The same run with
``--init latinhypercube`` keeps its **120 members** and at most
:math:`120 \times 101 = 12\,120` runs. A smaller search, ``--popsize 5``, gives
:math:`5 \times 8 = 40`, rounded up to **64 members**, so
``--popsize 5 --maxiter 20`` costs at most :math:`64 \times 21 = 1\,344` runs.
Fixing parameters shrinks :math:`N` and with it the population: four fixed
parameters leave :math:`N = 4`, so ``--popsize 15`` gives
:math:`15 \times 4 = 60`, rounded up to **64 members**.

Two things make the real count lower. Members whose weights violate
:math:`w_1 + w_2 \leq 1` are skipped by the optimizer without a model run and
leave no record. And the search stops as soon as the objective values of the
population agree: SciPy compares their standard deviation with its default
tolerance of 1% of their mean, and skips the comparison while any member of
the population is still infeasible. A search that converges this way stops
before ``--maxiter`` is reached. Polishing works the other way and adds
evaluations after the last generation.

The number of members and the resulting upper bound are logged when the
calibration starts, so the budget can be checked before the machine is
committed to it:

.. code-block:: console

   Calibrating 8 free parameter(s) with 128 population member(s) per generation and at most 100 generation(s): up to 12928 model run(s), on 15 worker process(es).

The size of the population the search actually built is recorded as
``population_size`` in :file:`result.json`, together with the number of
evaluations and of generations it really spent. That number, and not the
announced one, is what ran.

Inputs
------

The observed series
```````````````````

``--observed`` takes one file, in either of two layouts, recognized from its
content: a first line carrying the ``;`` separator is read as the CSV table of
the model, anything else as a PCRaster time series.

The **CSV layout** is the one the model writes for its own time series tables:
``;`` as the separator, a header whose first cell is ``0`` and whose remaining
cells are the station ids, and one row per time step carrying the step number
in the first column and one value per station:

.. code-block:: console

   0;1;2;3
   1;12.4;3.1;0.8
   2;15.9;4.0;1.2
   3;-9999;4.4;1.0

The first cell of that header is the label of the step column: ``0`` in the
tables the model writes, or any non-numeric word in a table written by hand. A
first cell that is another number is a row of values, which means the file has
no header; it is refused, naming both layouts.

The **PCRaster TSS layout** is its documented form: a title line such as
``timeseries scalar``, the number of columns, one line per column name
beginning with the time step column, and then one whitespace separated row per
time step:

.. code-block:: console

   timeseries scalar
   4
   timestep
   1
   2
   3
   1 12.4 3.1 0.8
   2 15.9 4.0 1.2

The header is required. A time series file without it is refused rather than
read with columns numbered ``1``, ``2``, ...: the columns of a time series are
stations, nothing in a head-less file says which station a column belongs to,
and a numbering would quietly compare the observations of one gauge with the
simulation of another. Adding the header to a file that lacks one is a title, a
count and one line per column, and the refusal names the layout it expects.

.. note::

   The station ids must be the ids of the sample locations of the
   configuration. The easiest way to get the layout and the ids right is to run
   the configuration once and use the table the run wrote as the template of
   the observed file: :file:`tss_arn.csv` for the default ``point``
   aggregation, :file:`tss_arn_subcatchment.csv` or :file:`tss_arn_zones.csv`
   for the other two. With ``zones`` the ids are the renumbered columns
   ``1..N``, and the correspondence with the original zone ids is written to
   :file:`zones_mapping.csv` in the output directory.

Gaps are written as they come: ``-9999``, any other negative marker, an empty
cell or a word that is not a number. The mask of `Which values count`_ is what
decides, so nothing has to be converted before a file is handed over.

The configuration must name the raster the aggregation samples from — the
sample locations raster for ``point`` and ``subcatchment``, the zones raster
for ``zones``. A configuration that does not name the raster its aggregation
needs is refused before any run: there would be no station to compare.

A fixed drainage network
````````````````````````

When the configuration does not provide a Local Drain Direction raster, the
model derives one from the digital elevation model with PCRaster's
``lddcreate``. On the real basin DEMs that operation is not deterministic: two
runs of the same configuration produce drainage networks that differ in a few
cells, and the accumulated runoff ``arn``, which is routed over the network,
therefore differs between them. The other eight output variables are computed
cell by cell and are unaffected.

A calibration on ``arn`` without a fixed network would compare series routed
over different networks from one evaluation to the next, and the differences
between candidates would be partly noise. **Calibrating on** ``arn``
**requires** ``RASTERS.ldd`` **to name a fixed LDD raster.** Generate it once,
with the DEM of the basin, and keep it with the other inputs:

.. code-block:: python

   import pcraster as pcr

   pcr.setclone("/basins/ipojuca/input/maps/clone.map")
   dem = pcr.readmap("/basins/ipojuca/input/maps/dem.map")
   ldd = pcr.lddcreate(dem, 1e31, 1e31, 1e31, 1e31)
   pcr.report(ldd, "/basins/ipojuca/input/maps/ldd.map")

.. code-block:: json

   {
      "RASTERS": {
         "ldd": "/basins/ipojuca/input/maps/ldd.map",
      },
   }

The same applies beyond ``arn`` when the time series are aggregated over
subcatchments: the subcatchment of each sample location is delineated over the
drainage network, so the areas the series are averaged over move with it, for
every variable.

Inputs the validation rejects
`````````````````````````````

The inputs are validated **once**, when the calibration loads the
configuration; the worker processes never revalidate them, since they do not
change during the search. A blocking problem therefore stops the calibration
before the first model run, which is the point: a search is hundreds or
thousands of runs, and an input the validation refuses would spend all of them
on a result that cannot be trusted.

``--allow-blocking-problems`` searches anyway. The checks still run and every
problem is still reported — the non-blocking ones as warnings, the blocking
ones as errors — and the search then starts instead of stopping. It is the
counterpart of ``rubem run --allow-blocking-problems``, and there is no ``-s``
on ``calibrate`` for it to conflict with.

The value is written to :file:`result.json`, under ``settings``, because it
changes what the numbers beside it mean: the parameters were fitted on inputs
the validation rejected, and nothing else in the artifacts would say so.

.. warning::

   The option does not repair anything. A raster the validation blocks on still
   reaches the model at every one of the evaluations, and the efficiency the
   search maximizes is measured on what that produced. Whether the defect
   reaches the compared stations is worth answering before the machine is
   committed: a single ``rubem run --allow-blocking-problems`` writes the time
   series of the stations, and values that are finite and plausible there say
   the search has something real to fit.

Artifacts of a run
------------------

What the run directory, ``-o``/``--run-dir``, receives. The tables of the
stations use ``;`` as their separator, the one the model writes its own tables
with; :file:`evaluations.csv` is comma-separated.

:file:`observed.csv`
   Written **before** the search, one row per station of the observed series,
   with the columns ``station``, ``in_selection``, ``pairs_in_window``,
   ``dropped``, ``mean``, ``std``, ``min`` and ``max``. ``in_selection`` says
   whether the station is one the objective averages over, which is every
   station without ``--stations``; a station of the observed file the
   configuration does not sample is listed here all the same, and never reaches
   the objective. ``pairs_in_window`` is how many of the compared steps it
   observes with a value the mask accepts, ``dropped`` how many values on those
   steps the mask rejected as gaps, and the remaining columns summarize the
   values that were kept. It is what a mean efficiency is
   read against afterwards, and it costs nothing to look at first.

:file:`evaluations.csv`
   One row per evaluation, with the columns ``id``, ``pid``, ``started_at``,
   ``alpha``, ``beta``, ``w_1``, ``w_2``, ``w_3``, ``rcd``, ``f``,
   ``alpha_gw``, ``x``, ``nse``, ``objective``, ``elapsed_seconds`` and
   ``error``; the `MODFLOW parameters`_ a run searched or fixed follow ``x``.
   ``id`` identifies the evaluation, ``pid`` the process that made it and
   ``started_at`` the wall-clock moment it began, in UTC; ``nse`` is
   empty for a candidate that produced no efficiency; ``error`` is empty for a
   successful evaluation, ``inadmissible`` for a candidate rejected without a
   run, and the type and message of the exception for a run that failed. The
   rows are ordered by the candidate they evaluated, not by the moment they
   were written, so that the table does not depend on how the parallel workers
   happened to finish — and ``started_at`` is what puts them back in the order
   they were made in, which is the order a convergence curve is drawn in.

:file:`stations.csv`
   The goodness of fit of the best candidate, one row per station the two
   series share, with the columns ``station``, ``in_selection``, ``pairs``,
   ``mean_observed``, ``std_observed``, ``mean_simulated``, ``std_simulated``,
   ``r`` (Pearson correlation), ``rmse`` and ``nse``. The statistics are the
   ones the evaluation of that candidate recorded, not a recomputation, so the
   table and the record always agree. A station outside the selection is
   measured like any other and marked as such: this is where the validation
   gauges are read.

:file:`best_<variable>.csv`
   The series behind the reported efficiency: the column ``step``, then
   ``observed_<id>`` and ``simulated_<id>`` for every shared station, one row
   per compared step. The steps and the stations are the ones the objective
   compared, and a value either series does not offer is left as an empty cell.
   The search keeps no output of its own — every evaluation writes into a
   temporary directory that is removed again — so the winning candidate is run
   once more, after the search, to produce this table. It is the last thing the
   run does before the summary, so a failure of that final run is reported with
   :file:`stations.csv` and the calibrated configuration already written and
   :file:`result.json` not written at all; the search itself has finished and
   its table is complete.

:file:`result.json`
   The summary: ``best_parameters`` (the nine parameters, the derived ``w_3``
   included, then the MODFLOW parameters searched or fixed), ``best_nse``,
   ``best_objective``, ``nfev`` and ``nit`` (the evaluations and generations
   the search spent), ``success`` and ``message`` from the optimizer,
   ``population_size``, an ``artifacts`` object naming every file above, and a
   ``settings`` object with ``variable``,
   ``spinup_steps``, ``maxiter``, ``popsize``, ``seed``, ``workers``,
   ``temp_dir``, ``init``, ``strategy``, ``mutation``, ``recombination``,
   ``polish``, ``bounds``, ``fixed`` and ``stations``. The workers, the
   temporary directory and the bounds are the values the run resolved and used
   — the bounds one entry per searched parameter, the settings ranges already
   narrowed — and not the defaults left unset on the command line, so the
   summary describes a calibration that can be repeated.

:file:`<config>-calibrated.json`
   The calibrated configuration: the input document with the best parameters
   in place, written in the format the input was written in, legacy or
   format 1.0. Its paths are the ones the loader resolved, which are absolute
   even when the input file wrote them relative to its own directory; moving
   the file to another machine therefore means fixing the paths. The MODFLOW
   parameters of the best candidate replace the ones of its section, and a
   conductivity table with a calibrated class is written next to it as
   :file:`<config>-calibrated-kh<n>.tbl`, which the calibrated configuration
   points at.

Next to them, the :file:`evaluations/` directory holds one JSON record per
evaluation, written by the worker that made it. A record carries what the CSV
row carries and, in addition, ``station_metrics``, the statistics of
:file:`stations.csv` for every station of that evaluation, and ``station_nse``,
the efficiencies alone — which is where to look when the mean hides one station
behaving differently from the others, for a candidate that is not the best one.

.. warning::

   A run directory that already holds evaluation records of an earlier
   calibration is refused before the search starts: consolidating two runs into
   one table would mix them. Use an empty run directory for every calibration,
   and keep the finished ones.

An interrupted run
``````````````````

A search that is interrupted, or that dies, after its first evaluation still
leaves the evaluations it made: the records are already on disk, and they are
consolidated into :file:`evaluations.csv` on the way out, with a message saying
where they are. Together with the :file:`observed.csv` written before the
search and the records themselves, that is the whole history of the run. What
needs the finished search is not written: :file:`result.json`,
:file:`stations.csv`, :file:`best_<variable>.csv` and the calibrated
configuration. Since a run directory is never reused, an interrupted run is
read from its table and a new directory is used for the next attempt.

Process model of the calibration
--------------------------------

The parent process loads the configuration once and validates its input files
once. The workers do not validate them again: they do not change during the
calibration, and re-reading every raster of the basin per evaluation would
dominate the cost.

Every evaluation then runs in a **fresh interpreter**. PCRaster keeps its state
process-wide — ``setclone`` is global to the process and the raster memory of a
run is not reclaimed — so a worker reused for a second evaluation would carry
the state of the first. The pool is therefore started with the ``spawn`` method
and configured for one task per worker: a worker starts, evaluates one
candidate and exits. The generation is spread over as many such workers as
``--workers`` allows, which is also what makes the calibration parallel at all.

Each worker builds the configuration of its candidate from the document of the
calibrated configuration: the nine parameters become the candidate's (and so do
the `MODFLOW parameters`_ of the run), the output directory becomes a temporary
directory of its own under ``--temp-dir``,
every raster series is disabled (an evaluation reads no raster of a previous
run, and writing them would dominate the cost of the run) and the time series
are reduced to the calibrated variable, as CSV. The aggregation the user
configured is kept, since it decides which areas the observed stations
correspond to. The temporary directory is removed when the evaluation ends,
whether it succeeded or not.

The workers are silenced: a null handler on the root logger keeps the warnings
of a configuration that is not validated again out of the terminal, and
standard output is pointed at the null device so that the newline the PCRaster
framework writes when an interpreter exits is not printed once per evaluation.
Nothing is lost: a failure of an evaluation is recorded in that evaluation's
JSON record and in its row of the table, and the parent logs one summary at the
end saying how many evaluations failed and what the first failure was. One
failing candidate never ends a calibration; it is ranked behind every candidate
that was evaluated.

What a run prints
`````````````````

The progress of a calibration goes to the ``rubem.progress`` logger, which the
command line prints on standard output, exactly as it does for a simulation; a
calibration started from Python says nothing until its host configures that
logger. Four kinds of line are written, in this order:

.. code-block:: console

   The calibration compares 216 time step(s); the observed series covers 216 of them, the step(s) 13 to 228.
   Station 1: 198 observed value(s) on the compared steps, 18 dropped as gaps.
   Station 2 (not in the objective): 204 observed value(s) on the compared steps, 12 dropped as gaps.
   Calibrating 8 free parameter(s) with 128 population member(s) per generation and at most 100 generation(s): up to 12928 model run(s), on 15 worker process(es).
   Generation 1: best objective 1.60757e+06, best NSE 0.601240, 256 evaluation(s) recorded.
   Generation 2: best objective 4.21033e+05, best NSE 0.794900, 384 evaluation(s) recorded.
   Calibration finished after 2048 evaluation(s) in 16 generation(s): best objective 160757, best NSE 0.873210.

The coverage lines say how much of the compared window the observations offer,
per station, and which stations the objective leaves out. The budget line is
the arithmetic of `The evaluation budget`_. A generation line reports the best
objective the optimizer holds and, beside it, the best efficiency among the
records the workers have written so far, with how many evaluations have been
recorded; a best objective of ``1e+30`` means no candidate has been evaluated
successfully yet. The closing line repeats the search as SciPy reports it.

Everything else — the fixed parameters, the narrowed ranges, the stations of
the objective, the warnings about a starting point moved onto a bound, and the
summary of the failed evaluations — goes to the ``rubem.calibration`` logger.
The command line shows its warnings; its informational records need a logging
configuration that asks for them.

When a worker is killed
```````````````````````

A worker that disappears before it finishes its evaluation ends the
calibration, and the most common reason is the system killing it for lack of
memory: every worker holds the rasters of one model run. The message says so,
advises a lower ``--workers`` and names the table of the evaluations made up to
that point, which is written on the way out. With MODFLOW enabled it also names
the other cause, a solver failure before the last time step of a stress period
when ``dis.nstp`` is above 1 (see `MODFLOW parameters`_).

Definitions worth knowing
-------------------------

Five things about the method that are easier to read once than to infer from a
table of results.

The weights are derived exactly
   ``w_3`` is computed as :math:`1 - (w_1 + w_2)`, a single subtraction, so the
   three weights of a candidate add up to 1 exactly and no candidate is ever
   run with weights that do not. There is no tolerance and no penalty term: a
   pair of weights that would leave ``w_3`` outside its range is not scored at
   all, it is rejected before the model runs.

A time step is a month
   The model computes a monthly water balance, so the steps the efficiency is
   computed on are the months of ``SIM_TIME``, and a window of 228 steps is
   nineteen years. The steps carry the numbers the model gives them, counted
   from the alignment month of the raster series rather than from the start of
   the simulated period, so the first compared step need not be ``1``.
   ``--spinup-steps`` drops steps by that number, and the coverage line the run
   prints says which steps are left.

A ``point`` station should mark one cell
   The value a time series carries for a station is the average over all the
   cells that carry that id in the sample locations raster. With the ``point``
   aggregation a station is meant to be a gauge, so its id should mark exactly
   one cell; an id painted over several cells is compared as the mean of them,
   which is a different quantity from the discharge of a gauge. The
   ``subcatchment`` and ``zones`` aggregations are the ones that average an
   area on purpose.

The reported best was really run
   The best candidate is one the search evaluated: its row is in
   :file:`evaluations.csv`, with the objective the run produced. Nothing is
   extrapolated, interpolated or reconstructed from the population, and
   :file:`stations.csv` repeats the statistics of that very evaluation.

The efficiency of the winner, station by station
   :file:`stations.csv` has it, one row per station, with ``in_selection``
   separating the gauges that drove the search from the ones that only watched.
   The same numbers are in the JSON record of that evaluation, under
   ``station_metrics`` and ``station_nse``, and :file:`best_<variable>.csv`
   holds the two series the numbers come from, ready to plot.

Running on a cluster or a large machine
---------------------------------------

The cost of a calibration is the number of model runs times the cost of one
run, divided by the number of workers. Measure the second factor before
committing a machine: one ``rubem run`` of the configuration is an upper bound
on one evaluation, which writes no raster series and does not validate the
inputs again, and so costs a little less. On the Ipojuca basin, 228 monthly
time steps, an evaluation is of the order of half a minute. At 25 seconds
each, a default search on that basin, up to 12,928 runs on 15 workers, is on
the order of six hours; ``--popsize 5 --maxiter 20``, up
to 1,344 runs, is well under an hour.

``--workers``
   Defaults to one less than the number of CPUs, which leaves a core for the
   parent. On a shared machine, or under a batch scheduler, set it to the
   number of cores the job was actually given rather than letting it read the
   whole machine. Each worker holds one model run in memory, plus the parent,
   so the memory of the job is roughly ``--workers`` times the memory of a
   single ``rubem run`` of the same configuration; that, and not the core
   count, is usually what limits the number of workers on a large basin, and a
   job that asks for more workers than its memory allows is stopped by the
   system killing one of them.

``--temp-dir``
   The per-evaluation output directories are created here. Point it at fast
   local storage of the node — the scratch directory of the job, not a shared
   network filesystem: every evaluation creates a directory, writes a small
   table into it and removes it again, and a network filesystem turns that into
   the slowest part of the evaluation. The run directory itself may stay on
   shared storage; it receives one small JSON record per evaluation.

Shorten the simulation period first
   An exploratory calibration over a few months of ``SIM_TIME``, with a small
   ``--popsize`` and ``--maxiter``, costs a fraction of the full search and
   still shows whether the observed series, the station ids and the spin-up are
   set up as intended. Move to the full period only once a short run finishes
   and produces a sensible efficiency.

Fix and narrow what is already known
   ``--fix`` removes a dimension from the search and ``--bound`` shrinks one.
   Both make a given budget go further on the parameters that are still open,
   and both are recorded in :file:`result.json`, so a run calibrated with part
   of its parameters pinned still says which ones and at what value.

Continue from a calibrated configuration
   :file:`<config>-calibrated.json` is an ordinary configuration file. Passing
   it back to ``rubem calibrate`` as ``-c`` starts a second search from the
   parameters the first one found, since the starting point of a search is the
   parameter set of the configuration it is given — useful to refine a result
   with a different seed, a longer period or a larger population.

Keep the run directory
   :file:`evaluations.csv`, :file:`observed.csv`, :file:`stations.csv`,
   :file:`best_<variable>.csv` and :file:`result.json` are the record of how a
   parameter set was obtained: the settings, the seed, the number of
   evaluations, what the observations offered and the whole response surface
   the search sampled. They are small, and they are what makes a published
   calibration reproducible.

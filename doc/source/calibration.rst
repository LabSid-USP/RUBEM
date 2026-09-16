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
how to budget a run, the inputs it needs, what it writes, and how it uses the
machine it runs on.

What the calibration fits
-------------------------

The model has nine calibration parameters, the ``CALIBRATION`` section of the
configuration file: :math:`\alpha`, :math:`b`, :math:`w_1`, :math:`w_2`,
:math:`w_3`, :math:`RCD`, :math:`f`, :math:`\alpha_{GW}` and :math:`x`. They
are described in :ref:`overview:Calibration and Validation`. The search covers
eight of them; the slope factor weight :math:`w_3` is not searched but derived
from the other two weights, because the three weights of the potential runoff
coefficient must add up to 1.

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
the results depend on, it changes the nine parameters and nothing else.

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
it is not finite (``NaN`` and the infinities), when it is ``-9999``, the gap
marker of the model's own tables and of the usual observation tables, or when
it is at or above ``1e30``.

That last threshold is how the PCRaster missing value ``1e31`` is masked. The
value does not round-trip exactly through ``Float32`` — written and read back
it becomes ``9.999999...e30`` — so the mask rejects everything at or above
``1e30`` instead of comparing with the constant. No streamflow or runoff of a
real basin comes anywhere near that magnitude. An empty cell, or a cell that is
not a number at all, is read as ``NaN`` and masked the same way.

Stations and the average
````````````````````````

The two series are aligned on the station ids they share and on the time steps
they share; a station or a step present on one side only is ignored.

A station has no efficiency when fewer than two of its pairs count, or when all
of its valid observations are equal: a constant record has no variability
for the efficiency to explain and would divide by zero. Such a station is
reported as having no efficiency and is left out of the average, instead of
dragging it. The efficiency of a candidate is the mean over the stations that
do have one.

A mismatch between the observations and the configuration — no station id in
common, no time step in common after the spin-up, or no shared station with an
efficiency — is not a poor candidate. It is not caught before the search
either: the comparison happens inside the evaluation, after that evaluation has
run the whole simulation. The evaluation is then recorded with the message of
the error in its ``error`` column and with the objective ``1e30``, like any
other failure, and the search carries on. The calibration ends with an error
only once no evaluation of the whole run has succeeded.

.. warning::

   A wrong station id is therefore paid for in model runs before it is
   reported. The per-generation log line is the early sign: a best objective of
   ``1e+30`` from the first generation on means that every candidate failed.
   Check the observed file against a run of the configuration first, over a few
   time steps, as `Running on a cluster or a large machine`_ describes.

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
   parameter.

The ninth parameter is derived rather than searched:

.. math::
   :label: calibration-w3
   :nowrap:

    \[w_3 = 1 - \left(w_1 + w_2\right)\]

so the search is eight-dimensional under the linear constraint
:math:`w_1 + w_2 \leq 1`. The constraint is handed to the optimizer, which
checks it before the objective and never spends a model run on a candidate
whose slope factor weight would come out negative. The derived weight must also
lie inside its own range, :math:`0 \leq w_3 \leq 1`; a candidate for which it
does not is rejected without a run and recorded with the error
``inadmissible``. Both checks are guards rather than a part of the search: the
optimizer keeps its trial vectors inside the bounds and drops the ones that
violate the constraint, so it does not propose an inadmissible candidate of its
own.

The starting point of the search, ``x0``, is the parameter set of the
configuration being calibrated. The optimizer places it in the initial
population, so the configuration's own parameters are always among the
candidates of the first generation and a calibration can never return something
worse than what it started from without the table showing why.

The search
----------

Settings
````````

The search is SciPy's ``differential_evolution`` with the following settings,
which the command does not expose because they describe the method rather than
the run:

``strategy="best1exp"``
   The trial vector is built from the best member of the population plus a
   scaled difference of two random members, with exponential crossover. A
   best-based strategy exploits the best candidate found so far and converges
   in fewer generations than the random-base ones [STORN1997]_, at some cost in
   exploration, which the dithered mutation below offsets. Fewer generations is
   what matters when one evaluation is a full simulation.

``init="sobol"``
   The initial population is a Sobol' sequence over the bounds instead of a
   random or Latin hypercube sample: it covers the eight-dimensional box far
   more evenly, so the initial sample is not wasted on clusters and gaps.

``mutation=(0.5, 1.0)``
   A pair, not a number: the mutation constant is drawn anew for every
   generation between the two values (*dithering*). It widens the range of step
   sizes the search takes without any tuning and reduces the chance of
   stagnating in a local optimum.

``recombination=0.7``
   The probability with which a trial vector keeps a component of the mutant
   rather than of its parent. A high value suits parameters that interact, as
   the three weights and the runoff coefficients do.

``polish=False``
   No local refinement of the best candidate at the end. The local search would
   spend model runs estimating gradients of an objective that is read back from
   a simulated table, which does not provide them reliably.

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

The evaluation budget
`````````````````````

The number of population members is not ``--popsize``: it is

.. math::
   :label: calibration-members
   :nowrap:

    \[members = \max\left(5,\ popsize \times 8\right)\]

with 8 the number of free parameters, rounded up to the next power of two,
because a Sobol' sequence is balanced only over a power-of-two sample. Every
generation evaluates one candidate per member, and the initial population is
one more round of evaluations on top of ``--maxiter`` generations, so

.. math::
   :label: calibration-runs
   :nowrap:

    \[runs \leq members \times \left(maxiter + 1\right)\]

With the defaults, ``--popsize 15`` gives :math:`15 \times 8 = 120`, rounded up
to **128 members**, and ``--maxiter 100`` gives at most
:math:`128 \times 101 = 12\,928` model runs. A smaller search, ``--popsize 5``,
gives :math:`5 \times 8 = 40`, rounded up to **64 members**, so
``--popsize 5 --maxiter 20`` costs at most :math:`64 \times 21 = 1\,344` runs.

Two things make the real count lower. Members whose weights violate
:math:`w_1 + w_2 \leq 1` are skipped by the optimizer without a model run and
leave no record. And the search stops as soon as the objective values of the
population agree: SciPy compares their standard deviation with its default
tolerance of 1% of their mean, and skips the comparison while any member of
the population is still infeasible. A search that converges this way stops
before ``--maxiter`` is reached.

The number of members and the resulting upper bound are logged when the
calibration starts, so the budget can be checked before the machine is
committed to it:

.. code-block:: console

   Calibrating 8 free parameter(s) with 128 population member(s) per generation and
   at most 100 generation(s): up to 12928 model run(s), on 15 worker process(es).

The size of the population the search actually built is recorded as
``population_size`` in :file:`result.json`, together with the number of
evaluations and of generations it really spent.

Inputs
------

The observed series
```````````````````

``--observed`` takes one file, in either of two layouts, recognized from its
content.

The **CSV layout** is the one the model writes for its own time series tables:
``;`` as the separator, a header whose first cell is ``0`` and whose remaining
cells are the station ids, and one row per time step carrying the step number
in the first column and one value per station:

.. code-block:: console

   0;1;2;3
   1;12.4;3.1;0.8
   2;15.9;4.0;1.2
   3;-9999;4.4;1.0

The **PCRaster TSS layout** is accepted as well, both in its documented form (a
title line, the number of columns, one line per column name, then the rows) and
in the header-less form the model itself writes, whose stations are then
numbered ``1``, ``2``, ... in column order.

.. note::

   The station ids must be the ids of the sample locations of the
   configuration. The easiest way to get the layout and the ids right is to run
   the configuration once and use the table the run wrote as the template of
   the observed file: :file:`tss_arn.csv` for the default ``point``
   aggregation, :file:`tss_arn_subcatchment.csv` or :file:`tss_arn_zones.csv`
   for the other two. With ``zones`` the ids are the renumbered columns
   ``1..N``, and the correspondence with the original zone ids is written to
   :file:`zones_mapping.csv` in the output directory.

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

Artifacts of a run
------------------

The three artifacts of the run directory, ``-o``/``--run-dir``:

:file:`evaluations.csv`
   One row per evaluation, with the columns ``id``, ``pid``, ``alpha``,
   ``beta``, ``w_1``, ``w_2``, ``w_3``, ``rcd``, ``f``, ``alpha_gw``, ``x``,
   ``nse``, ``objective``, ``elapsed_seconds`` and ``error``. ``id`` identifies
   the evaluation and ``pid`` the process that made it; ``nse`` is empty for a
   candidate that produced no efficiency; ``error`` is empty for a successful
   evaluation, ``inadmissible`` for a candidate rejected without a run, and the
   type and message of the exception for a run that failed. The rows are
   ordered by the candidate they evaluated, not by the moment they were
   written, so that the table does not depend on how the parallel workers
   happened to finish.

:file:`result.json`
   The summary: ``best_parameters`` (the nine parameters, the derived ``w_3``
   included), ``best_nse``, ``best_objective``, ``nfev`` and ``nit`` (the
   evaluations and generations the search spent), ``success`` and ``message``
   from the optimizer, ``population_size``, and a ``settings`` object with
   ``variable``, ``spinup_steps``, ``maxiter``, ``popsize``, ``seed``,
   ``workers``, ``temp_dir``, ``init``, ``strategy``, ``mutation``,
   ``recombination`` and ``polish``. The number of workers and the temporary
   directory are the values the run resolved and used, not the defaults left
   unset on the command line, so the summary describes a calibration that can
   be repeated.

:file:`<config>-calibrated.json`
   The calibrated configuration: the input document with the best parameters
   in place, written in the format the input was written in, legacy or
   format 1.0. Its paths are the ones the loader resolved, which are absolute
   even when the input file wrote them relative to its own directory; moving
   the file to another machine therefore means fixing the paths.

Next to them, the :file:`evaluations/` directory holds one JSON record per
evaluation, written by the worker that made it. A record carries what the CSV
row carries and, in addition, ``station_nse``, the efficiency of each
individual station — which is where to look when the mean hides one station
behaving differently from the others.

.. warning::

   A run directory that already holds evaluation records of an earlier
   calibration is refused before the search starts: consolidating two runs into
   one table would mix them. Use an empty run directory for every calibration,
   and keep the finished ones.

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
calibrated configuration: the nine parameters become the candidate's, the
output directory becomes a temporary directory of its own under ``--temp-dir``,
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
   count, is usually what limits the number of workers on a large basin.

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

Continue from a calibrated configuration
   :file:`<config>-calibrated.json` is an ordinary configuration file. Passing
   it back to ``rubem calibrate`` as ``-c`` starts a second search from the
   parameters the first one found, since the starting point of a search is the
   parameter set of the configuration it is given — useful to refine a result
   with a different seed, a longer period or a larger population.

Keep the run directory
   :file:`evaluations.csv` and :file:`result.json` are the record of how a
   parameter set was obtained: the settings, the seed, the number of
   evaluations and the whole response surface the search sampled. They are
   small, and they are what makes a published calibration reproducible.

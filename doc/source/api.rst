Python API
==========

``rubem.api`` runs the model from Python: it loads a configuration, runs the
simulation and reports what the run wrote.

Quickstart
----------

Run a configuration file, the same file the ``rubem run`` command takes:

.. code-block:: python

   from rubem.api import Model

   model = Model.from_file("config.json")
   result = model.run()
   print(result.output_directory)

Relative paths of the file are anchored on its directory, unless ``base_dir``
says otherwise. A configuration held in memory is passed as a dictionary
instead, in the legacy format or in format 1.0; a dictionary has no directory
of its own, so ``base_dir`` anchors its relative paths:

.. code-block:: python

   from rubem.api import ConfigurationError, Model

   try:
       model = Model.from_config(document, base_dir="/data/basin")
   except ConfigurationError as error:
       for problem in error.problems:
           print(problem)
       raise

The dictionary is copied when it is loaded, so it can be edited and passed
again to configure another model: each model keeps the document it was built
from, and runs it in either mode.

Both loaders validate the input files and their content unless
``validate_input=False`` is passed, and both raise ``ConfigurationError`` when
the validation finds blocking problems, a missing member of an input raster
series among them. Not every failed load is one of those: a file that is not
JSON raises ``json.JSONDecodeError``, a document whose sections do not match
the schema a pydantic ``ValidationError``, and a single raster or table that is
not there a ``FileNotFoundError``. The clone and the DEM are read while the
configuration is built, so they raise ``FileNotFoundError`` whether or not the
input is validated; with the validation off the other missing inputs surface
only when the run reaches them.

An already loaded ``ModelConfiguration`` may be passed to ``Model.from_config``
as well, and is used as it is, neither validated again nor re-anchored.

``Model.run_isolated`` runs the same simulation in a fresh subprocess:

.. code-block:: python

   result = model.run_isolated()

Either form returns a ``RunResult``, which describes the run from its
configuration rather than by listing the output directory, and whose paths are
absolute:

.. code-block:: python

   result.output_directory  # Path of the directory the run wrote to
   result.rasters           # {variable id: (raster member, ...)}, per enabled format
   result.time_series       # {variable id: (table, ...)}, the CSV and/or TSS tables
   result.metadata          # Path of metadata.json (format 1.0), or None
   result.first_step        # first simulated time step
   result.last_step         # last simulated time step
   result.elapsed_seconds   # wall-clock duration of the simulation itself

Stability
---------

``rubem.api`` is the public surface of the package: ``Model``, ``RunResult``
and ``ConfigurationError``. Every other module is internal and may change
without notice, including the classes the internal modules expose today
(``ModelConfiguration``, ``DynamicFrameworkWrapper`` and the rest).

While the version is below 1.0, a breaking change to ``rubem.api`` bumps the
minor version and is listed in the changelog.

``Model`` hands out the loaded ``ModelConfiguration``: the constructor takes
one, ``Model.from_config`` accepts one and the ``Model.configuration`` property
returns one, so that a caller that already holds a configuration can use it.
That object is internal all the same: it is reachable through the public
surface, but its own shape carries no stability guarantee.

Process model and limitations
-----------------------------

PCRaster keeps its state process-wide: ``setclone`` is global to the process
and the raster memory of a run is not reclaimed. Two consequences follow for
``Model.run``, which runs in the calling process:

* successive runs in one interpreter grow the resident memory;
* two runs must not happen at the same time in one process. Every run sets the
  clone for itself, so runs on different grids may follow one another; runs
  started from several threads, though, share that state while they are under
  way. On different grids one of them fails; on the same grid they may all
  finish and write wrong results, without any error. Parallel runs need one
  process each.

``Model.run_isolated`` avoids both: it runs the simulation in a subprocess
started with the ``spawn`` method, used for that one run and shut down before
the call returns. The configuration crosses as its document, its base
directory and the validation flag, and is rebuilt on the other side; the result
crosses as plain data. A ``ConfigurationError`` raised while the subprocess
rebuilds the configuration reaches the caller as the same exception, with its
problems; any other exception of the run propagates as itself, and a subprocess
that dies before the run finishes is reported as a ``RuntimeError``. Every call
pays a full interpreter start-up, which is the price of keeping the state of
PCRaster out of the caller.

A caller that only uses ``run_isolated`` never loads PCRaster itself: the
library is imported in the subprocess alone. GDAL is a different matter:
loading a configuration imports it, whether or not the inputs are validated.

The ``spawn`` method imports the main module of the caller in the subprocess,
as it does for any :mod:`multiprocessing` worker, so a script that calls
``run_isolated`` must guard its entry point:

.. code-block:: python

   if __name__ == "__main__":
       result = Model.from_file("config.json").run_isolated()

For the same reason the script must be a file. One read from standard input
(``python - < script.py``) has no file for the subprocess to import, and on
Python 3.13 and 3.14 the subprocess fails at start-up; a command passed with
``-c`` is fine. Both mistakes, the missing guard and the script on standard
input, kill the subprocess before the run starts and reach the caller as the
``RuntimeError`` above, whose message names them; the error of the subprocess
itself is on standard error.

``run_isolated`` waits for its subprocess. An interrupt that reaches the
subprocess as well, as Ctrl-C in a terminal does, stops the run and raises
``KeyboardInterrupt`` at once. An interrupt delivered to the calling process
alone (``kill -INT`` on its pid, or a scheduler that signals only the process it
started) is raised only after the subprocess has finished the run.

Importing ``rubem.api`` does not require PCRaster or GDAL; running the model
does. Without them, loading a configuration or running raises ``ImportError``
with the same installation guidance the command line prints.

Parallel runs
-------------

Parallel runs need one process each. The form to use is a process pool of the
caller, with ``Model.run`` called inside every worker:

.. code-block:: python

   import multiprocessing
   from concurrent.futures import ProcessPoolExecutor

   from rubem.api import Model


   def simulate(path):
       return Model.from_file(path).run()


   if __name__ == "__main__":
       paths = ["basin_a/config.json", "basin_b/config.json", "basin_c/config.json"]
       context = multiprocessing.get_context("spawn")
       with ProcessPoolExecutor(max_workers=2, mp_context=context) as pool:
           for result in pool.map(simulate, paths):
               print(result.output_directory)

The model is built inside the worker, so what crosses the boundary is the path
(or the configuration dictionary) on the way in and the ``RunResult`` on the way
back; a ``ConfigurationError`` of a worker reaches the caller as itself, with
its problems. Give every run its own output directory.

A worker is reused from one run to the next, on the same grid or on another, so
the interpreter start-up is paid once per worker and not once per run, which is
what makes the pool cheaper than calling ``run_isolated`` from several threads.
The memory of a reused worker grows with its runs, as it does for any
in-process run; ``max_tasks_per_child`` bounds it. ``spawn`` is the start method
``run_isolated`` uses and the one available on every platform, and the entry
point guard above applies to it.

A thread pool is not a substitute: threads that call ``Model.run`` share the
state of PCRaster, with the consequences described above.

Calibration
-----------

``rubem calibrate`` is built on this API: each of its workers calls
``Model.run()`` in its own process, on a configuration derived from the one
being calibrated. The same search is available from Python as
``rubem.calibration.runner.calibrate``, which takes the configuration file, the
observed series, the run directory and a ``CalibrationSettings``:

.. code-block:: python

   from rubem.calibration.runner import CalibrationSettings, calibrate

   if __name__ == "__main__":
       result = calibrate(
           "config.json",
           "observed.csv",
           "calibration",
           CalibrationSettings(seed=42, maxiter=20, popsize=5),
       )
       print(result.best_parameters, result.best_nse)

The entry point guard is required: the calibration starts its workers with the
``spawn`` method, which imports the main module of the caller in every one of
them. SciPy is needed as well, from the ``rubem[calibration]`` extra.

``rubem.calibration`` is **not** part of the stable surface yet: only
``rubem.api`` is, and the calibration package may change without a minor
version bump until it is promoted. The method behind the command is documented
in :doc:`Calibration </calibration>`.

Logging
-------

The package reports its progress through the ``rubem`` logger and writes
nothing to standard output of its own. Configure that logger to follow a run:

.. code-block:: python

   import logging

   logging.basicConfig(level=logging.INFO)
   logging.getLogger("rubem").setLevel(logging.INFO)

This configures the calling process, and an isolated run happens in another
one: the records of the simulation are emitted in the subprocess, which starts
from the default logging configuration and does not inherit the handlers of the
caller. What the calling process does reaches the configured handlers, loading
the configuration included, since the loaders run there; the run itself does
not.

Two things on standard output are not this package's to suppress. The PCRaster
framework registers an ``atexit`` hook that writes a single newline when the
interpreter exits, in the caller for an in-process run and in the subprocess
for an isolated one; the subprocess shares the standard output of the caller
and exits with every call, so a batch of isolated runs writes one newline per
run. And at level ``DEBUG`` an in-process run asks the framework for its own
progress output, which it writes to standard output as one dot per time step;
at ``INFO`` it is silent, and an isolated run is silent at any level, its
subprocess starting from the default configuration.

Module reference
----------------

.. autoexception:: rubem.api.ConfigurationError
   :members:

The reference below covers the internal modules as well, because the model is
documented from them; only ``rubem.api`` is stable.

.. autosummary::
   :toctree: generated
   :template: custom-module-template.rst
   :recursive:

   rubem.api
   rubem.cli
   rubem.configuration
   rubem.core
   rubem.file
   rubem.hydrological_processes
   rubem.validation

.. note::

   The ``rubem.preprocessing`` helpers are not part of the documented API
   yet; they will be added when the preprocessing tools are reworked.

"""Entry points a spawned subprocess imports by name.

Those of ``Model.run_isolated``, and the worker of the process pool a caller
builds for its parallel runs.

A subprocess entry point is pickled by reference, so the child imports this
module to find the function it has to call. Nothing here imports the model at
module level: a probe must be able to look at the fresh interpreter before the
native libraries are loaded, which is what tells a spawned child from a forked
one.
"""

import json
import os
import sys
from pathlib import Path

MARKER_FILENAME = "child.json"


def record_and_run(document, base_dir, validate_input, allow_blocking_problems):
    """Record who runs the simulation, then delegate to the real entry point.

    Installed over ``rubem.api._run_document`` in the parent; the child
    unpickles this function by name and finds its own, unpatched
    ``rubem.api._run_document``, so the delegation below is not a loop.

    :param document: The configuration document.
    :param base_dir: Directory the relative paths of the document are anchored on.
    :param validate_input: Whether to validate the input files and their content.
    :param allow_blocking_problems: Whether to run past blocking problems.
    :return: The result of the run, as the plain data the boundary carries.
    """
    preloaded = sorted(name for name in ("pcraster", "osgeo") if name in sys.modules)

    from rubem import api

    result = api._run_document(document, base_dir, validate_input, allow_blocking_problems)
    marker = Path(document["DIRECTORIES"]["output"]) / MARKER_FILENAME
    marker.write_text(json.dumps({"pid": os.getpid(), "preloaded": preloaded}), encoding="utf8")
    return result


def simulate(config):
    """Build the model in this worker and run it here, as the documented pool does.

    :param config: The configuration document.
    :return: The pid of the worker and the result of the run.
    """
    from rubem.api import Model

    return os.getpid(), Model.from_config(config).run()


def die(document, base_dir, validate_input, allow_blocking_problems):
    """Kill the subprocess the way a crashing native library does.

    ``os._exit`` leaves no exception for the executor to send back, which is
    the situation ``Model.run_isolated`` has to report on its own.
    """
    os._exit(3)

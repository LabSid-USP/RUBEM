# Set default logging handler to avoid "No handler found" warnings.
import logging
from logging import NullHandler

logging.getLogger(__name__).addHandler(NullHandler())

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright (C) 2020-2023 - LabSid/PHA/EPUSP"
__license__ = "GPL"
__date__ = "2023-05-17"
__version__ = "0.2.2"
__release__ = f"{__version__}-beta.1"

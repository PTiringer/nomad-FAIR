# --- For Backward Compatibility ---
# Make all v1 contents available at the top level of the `basesections` package.
# Users can continue to do: from nomad.datamodel.metainfo.basesections import SomeV1Class
from nomad.datamodel.metainfo.basesections.v1 import *

# --- For Forward Compatibility and Clarity ---
# Import the v2 module itself, so it's available as a namespace.
# Users can explicitly access v2 content like this:
# from nomad.datamodel.metainfo.basesections import v2
from nomad.datamodel.metainfo.basesections import v2

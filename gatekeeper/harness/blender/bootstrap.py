# Gatekeeper Blender bootstrap.
#
# Invoked by `gd blender` / `gd asset` as:
#   blender -b --factory-startup --python bootstrap.py -- <generator.py> [args...]
#
# It puts `gdblend` on sys.path, normalises argv so the generator sees only its
# own arguments, then execs the generator in a __main__-like namespace. Any
# exception is printed as a GDMETRICS failure line so the caller always gets
# one machine-readable result.
import os
import runpy
import sys
import traceback

_lib = os.environ.get("GD_LIB")
if _lib and _lib not in sys.path:
    sys.path.insert(0, _lib)

_raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not _raw:
    print("GDMETRICS " + '{"ok": false, "error": "bootstrap: no generator script given"}')
    sys.exit(2)

_script, _args = _raw[0], _raw[1:]

import gdblend  # noqa: E402  (path must be set first)

gdblend.ARGV = list(_args)
gdblend.SCRIPT = _script
gdblend.reset_scene()

# The generator should see a normal argv: [script, *its own args]
sys.argv = [_script] + list(_args)

try:
    runpy.run_path(_script, run_name="__main__")
except SystemExit as e:
    if e.code not in (0, None):
        raise
except Exception:
    traceback.print_exc()
    gdblend.fail("generator raised: " + repr(sys.exc_info()[1]))
    sys.exit(1)

# A generator that never reported anything is a bug, not a success: the whole
# point of the pipeline is that every asset comes back with measurements.
if not gdblend.reported():
    gdblend.fail("generator finished without calling gdblend.report() - "
                 "no metrics means nothing can be gated on it")
    sys.exit(1)

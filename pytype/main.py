"""Tool for inferring types from Python programs.

'pytype' is a tool for generating pytd from Python programs.
See go/python-type-inference for details.

Usage:
  pytype [flags] file.py
"""

import logging
import optparse
import os
import sys

from pytype import infer
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import utils


log = logging.getLogger(__name__)


def parse_options(args):
  """Use optparse to parse command line options."""
  o = optparse.OptionParser()
  o.add_option(
      "-o", "--output", type="string", action="store",
      dest="output", default=None,
      help="Output file (default: <filename>.pytd). Use '-' for stdout.")
  o.add_option(
      "-V", "--python_version", type="string", action="store",
      dest="python_version", default="2.7",
      help=("Python version to emulate (\"major.minor\", e.g. \"2.7\")"))
  o.add_option(
      "-v", "--verbosity", type="int", action="store",
      dest="verbosity", default=1,
      help=("Set logging verbosity: "
            "-1=quiet, 0=fatal, 1=error (default), 2=warn, 3=info, 4=debug"))
  o.add_option(
      "-O", "--optimize", action="store_true",
      dest="optimize", default=False,
      help=("Optimize generated pytd"))
  o.add_option(
      "-A", "--api", action="store_true",
      dest="api", default=False,
      help=("Analyze all functions and classes, "
            "also those not called from anywhere."))
  o.add_option(
      "-S", "--structural", action="store_true",
      dest="structural", default=False,
      help=("Analyze all functions and classes, also those not called from "
            "anywhere. Output the result in structural form."))
  o.add_option(
      "-X", "--expensive", action="store_true",
      dest="expensive", default=True,
      help="Do a full path-sensitive analysis.")
  o.add_option(
      "--solve-unknowns", action="store_true",
      dest="solve_unknowns", default=False,
      help=("Run the solver to turn 'unknown' classes "
            "into builtins (only used for testing)"))
  o.add_option(
      "--svg-output", type="string", action="store",
      dest="svg_output", default=None,
      help="Output control flow graph as SVG.")
  o.add_option(
      "--pseudocode-output", type="string", action="store",
      dest="pseudocode_output", default=None,
      help="Output pseudo code.")
  o.add_option(
      "-e", "--explain", action="store_true",
      dest="explain", default=False,
      help=("For every omitted type, explain why it was impossible. "
            "Generates a lot of output."))
  o.add_option(
      "-r", "--reverse-operators", action="store_true",
      dest="reverse_operators", default=False,
      help=("Enable support for Python reverse "
            "operator overloading (__radd__ etc.)"))

  options, filenames = o.parse_args(args)
  return options, filenames


def main():
  options, filenames = parse_options(sys.argv)
  unused_executable = filenames.pop(0)
  if len(filenames) < 1:
    print >> sys.stderr, "Need at least one filename."
    sys.exit(1)
  elif len(filenames) >= 2:
    print >> sys.stderr, "Analyzing multiple files not yet supported:"
    print >> sys.stderr, " ".join(filenames)
    sys.exit(1)

  filename, = filenames

  log_levels = [logging.CRITICAL, logging.ERROR, logging.WARNING,
                logging.INFO, logging.DEBUG]
  if options.verbosity >= 0:
    if options.verbosity >= len(log_levels):
      print >> sys.stderr, "Invalid verbosity %s" % options.verbosity
      sys.exit(1)
    logging.basicConfig(level=log_levels[options.verbosity])
  else:
    # "verbosity=-1" can be used to disable all logging, so configure logging
    # accordingly.
    logging.basicConfig(level=logging.CRITICAL + 1)

  with open(filename, "r") as fi:
    src = fi.read()

  python_version = tuple(map(int, options.python_version.split(".")))
  if len(python_version) != 2:
    logging.error("--python_version must be <major>.<minor>")
    sys.exit(1)

  mod = infer.infer_types(
      src,
      python_version=python_version,
      filename=filename,
      deep=options.api or options.structural,
      solve_unknowns=options.solve_unknowns or options.api,
      expensive=options.expensive,
      svg_output=options.svg_output,
      explain=options.explain,
      pseudocode_output=options.pseudocode_output,
      reverse_operators=options.reverse_operators)

  log.info("=========== PyTD =============\n%s", pytd.Print(mod))
  if options.optimize:
    mod = optimize.Optimize(mod,
                            # TODO(kramm): Add FLAGs for these
                            lossy=False,
                            use_abcs=False,
                            max_union=7,
                            remove_mutable=False)
    log.info("=========== PyTD optimized =============\n%s", pytd.Print(mod))
  log.info("========================================")

  result = pytd.Print(utils.CanonicalOrdering(mod))
  if not result.endswith("\n"):  # TODO(pludemann): fix this hack
    result += "\n"
  if options.output == "-":
    sys.stdout.write(result)
  else:
    if options.output:
      output_filename = options.output
    else:
      output_filename = os.path.splitext(filename)[0] + ".pytd"
      print >> sys.stderr, "Writing output to %s" % output_filename
    with open(output_filename, "w") as fi:
      fi.write(result)


if __name__ == "__main__":
  main()

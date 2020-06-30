#!/usr/bin/python3
# -*- mode: Python; tab-width: 4; indent-tabs-mode: nil; -*-
"""
  Copyright (C) 2017 Marcus Geelnard

  This software is provided 'as-is', without any express or implied
  warranty.  In no event will the authors be held liable for any damages
  arising from the use of this software.

  Permission is granted to anyone to use this software for any purpose,
  including commercial applications, and to alter it and redistribute it
  freely, subject to the following restrictions:

  1. The origin of this software must not be misrepresented; you must not
     claim that you wrote the original software. If you use this software
     in a product, an acknowledgment in the product documentation would be
     appreciated but is not required.
  2. Altered source versions must be plainly marked as such, and must not be
     misrepresented as being the original software.
  3. This notice may not be removed or altered from any source distribution.
"""

import argparse
import os
import shlex
import subprocess
import sys

sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), "helpers"))
from filterblobs import filterblobs

_FILTER_COMMAND = ""
_FILE_EXT_FILTER = ["c", "cpp", "cxx", "cc", "h", "hpp", "hxx", "hh"]
_BLOB_SIZE_LIMIT = 200000
_DEFAULT_BRANCH = "master"


def _NAME_FILTER(file_name):
    if len(_FILE_EXT_FILTER) < 1:
        return True
    file_name_lower = file_name.lower()
    for ext in _FILE_EXT_FILTER:
        if len(file_name_lower) > len(ext) and file_name_lower.endswith(ext):
            if file_name_lower[len(file_name_lower) - len(ext) - 1] == ".":
                return True
    return False


def _BLOB_FILTER(file_name, blob):
    if len(blob) > _BLOB_SIZE_LIMIT:
        return blob
    cmd = shlex.split(_FILTER_COMMAND.replace("%f", file_name))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    res = p.communicate(input=blob)
    return res[0]


# Handle the program arguments.
parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description="Run a filter (command) on all files in the Git history of a repo, "
    "creating a new repo.",
)
parser.add_argument(
    "-f",
    "--file-filter",
    metavar="FILE-FILTER",
    help="file extension filter (comma separated list of extensions)\nDefault: "
    + ",".join(_FILE_EXT_FILTER),
)
parser.add_argument(
    "-l",
    "--size-limit",
    metavar="LIMIT",
    help="blob size limit in bytes (do not filter blobs larger than this)\nDefault: "
    + str(_BLOB_SIZE_LIMIT),
)
parser.add_argument(
    "-b",
    "--branch",
    metavar="BRANCH",
    help="main branch (will be checked out in the new repo)\nDefault: "
    + _DEFAULT_BRANCH,
)
parser.add_argument("input", metavar="INPUT", help="path to the source Git repo")
parser.add_argument("output", metavar="OUTPUT", help="path to the rewritten Git repo")
parser.add_argument(
    "filter",
    metavar="FILTER",
    help="blob filter command (a string)\nThe command will get the original data blob from STDIN,\n"
    "and the rewritten blob is expected on STDOUT.",
)
args = parser.parse_args()

_FILTER_COMMAND = args.filter
if args.file_filter:
    _FILE_EXT_FILTER = args.file_filter.lower().split(",")
if args.size_limit:
    _BLOB_SIZE_LIMIT = int(args.size_limit)
if args.branch:
    branch = args.branch
else:
    branch = _DEFAULT_BRANCH

print("Using file filter: %s" % (",".join(_FILE_EXT_FILTER)))
print("Blob size limit:   %d" % (_BLOB_SIZE_LIMIT))
print("Main branch:       %s" % (branch))

# Execute filter-blobs function.
filterblobs(args.input, args.output, _NAME_FILTER, _BLOB_FILTER, branch)

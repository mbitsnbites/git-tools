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
import shutil
import subprocess
import tempfile

_DEFAULT_BRANCH = "master"


# Clean out a directory.
def cleandir(path):
    for the_file in os.listdir(path):
        file_path = os.path.join(path, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(e)


# Get the Git log for a repository.
def getlog(path, branch, name):
    lines = subprocess.check_output(
        [
            "git",
            "-C",
            path,
            "log",
            "--first-parent",
            "--pretty=format:%H %ct %s",
            branch,
        ]
    ).split("\n")
    log = []
    for line in lines:
        sep1_pos = line.find(" ")
        sep2_pos = line.find(" ", sep1_pos + 1)
        sha = line[:sep1_pos]
        time = line[(sep1_pos + 1) : sep2_pos]
        subject = line[(sep2_pos + 1) :]
        log.append({"sha": sha, "time": int(time), "subject": subject, "name": name})
    return list(reversed(log))


# Combine logs in a commit-date order.
def combinelogs(log1, log2):
    log = []

    # Note: Just using a plain sort operation here would mess up the log if the
    # commit dates in any of logs are not in a chronological order.

    # As long as there are commits left in both logs, pick the oldest commit
    # first (sort).
    idx1 = 0
    idx2 = 0
    while idx1 < len(log1) and idx2 < len(log2):
        if log1[idx1]["time"] < log2[idx2]["time"]:
            log.append(log1[idx1])
            idx1 = idx1 + 1
        else:
            log.append(log2[idx2])
            idx2 = idx2 + 1

    # Append the remaining tail of whichever log has commits left.
    if idx1 < len(log1):
        log.extend(log1[idx1:])
    if idx2 < len(log2):
        log.extend(log2[idx2:])

    return log


def extractreponame(url):
    colon_pos = url.rfind(":")
    slash_pos = url.rfind("/")
    dot_pos = url.rfind(".")
    name_start = slash_pos if slash_pos > colon_pos else colon_pos
    name_end = dot_pos if dot_pos > name_start else len(url)
    return url[(name_start + 1) : name_end]


# Handle the program arguments.
parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description="Create a repo with one or more submodules.",
)
parser.add_argument(
    "-o",
    "--output",
    metavar="OUTPUT",
    required="True",
    help="output directory for the Git repo",
)
parser.add_argument(
    "-b",
    "--branch",
    metavar="BRANCH",
    help="main branch name\nDefault: " + _DEFAULT_BRANCH,
)
parser.add_argument(
    "sourcerepo", metavar="SOURCEREPO", nargs="+", help="URL for a source reppository"
)
args = parser.parse_args()

branch = args.branch if args.branch else _DEFAULT_BRANCH

# Clone all repos to a temporary working directory (to get the logs).
work_root = tempfile.mkdtemp()
log = []
repos = {}
try:
    # For each source repository...
    for url in args.sourcerepo:
        # Clone the source repo.
        repo_name = extractreponame(url)
        repo_path = os.path.join(work_root, repo_name)
        subprocess.check_call(["git", "clone", url, repo_path])
        repos[repo_name] = {"url": url, "added": False}

        # Get the log for this repo.
        src_log = getlog(repo_path, branch, repo_name)
        log = combinelogs(log, src_log)

finally:
    # Remove the temporary directory.
    cleandir(work_root)
    os.rmdir(work_root)

# Create the new repository.
out_root = args.output
if os.path.isdir(out_root):
    cleandir(out_root)
else:
    os.makedirs(out_root)
subprocess.check_call(["git", "-C", out_root, "init"])
subprocess.check_call(["git", "-C", out_root, "checkout", "-b", branch])

# Add all the commits from the log.
git_env = os.environ.copy()
for x in log:
    name = x["name"]
    repo_path = os.path.join(out_root, name)

    # Add the submodule for the first time, if necessary.
    if not repos[name]["added"]:
        print("Add submodule " + name)
        subprocess.check_call(
            ["git", "-C", out_root, "submodule", "add", repos[name]["url"], name]
        )
        repos[name]["added"] = True

    # Update the submodule to a specific commit.
    print("Update " + name + " to " + x["sha"])
    subprocess.check_call(["git", "-C", repo_path, "checkout", x["sha"]])
    subprocess.check_call(["git", "-C", out_root, "add", name])
    git_env["GIT_AUTHOR_DATE"] = str(x["time"])
    git_env["GIT_COMMITTER_DATE"] = str(x["time"])
    subprocess.check_call(
        ["git", "-C", out_root, "commit", "-m", name + ": " + x["subject"]], env=git_env
    )

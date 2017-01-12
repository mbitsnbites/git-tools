#!/usr/bin/python
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

import argparse, multiprocessing, os, shutil, subprocess, sys

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

def extractline(exp_str, pos):
    eol_pos = exp_str.find('\n', pos)
    if eol_pos >= 0:
        return (exp_str[pos:eol_pos], eol_pos + 1)
    else:
        return (exp_str[pos:len(exp_str)], len(exp_str))

# Parse an export string into a list of commands.
def parseexport(exp_str):
    current_pos = 0
    end_pos = len(exp_str)
    commands = []
    while current_pos < end_pos:
        # Get the next command.
        (cmd, current_pos) = extractline(exp_str, current_pos)
        if cmd:
            # Get the command type.
            space_pos = cmd.find(' ')
            if space_pos >= 0:
                cmd_type = cmd[:space_pos]
            else:
                cmd_type = cmd

            # Handle 'data'.
            if cmd_type == 'data':
                data_len = int(cmd[(space_pos + 1):])
                data_end = current_pos + data_len
                data = exp_str[current_pos:data_end]
                cmd = cmd + '\n' + data
                current_pos = data_end

            commands.append(cmd)

    return commands

# Generate an import string.
def makeimport(exp):
    return '\n'.join(exp) + '\n'

# Export a repository.
def exportrepo(repo_root):
    cmd = ['git', '-C', repo_root, 'fast-export', '--all']
    return parseexport(subprocess.check_output(cmd))

# Import to a new repository.
def importtorepo(repo_root, commands):
    # Generate a string from the export description.
    import_str = makeimport(commands)

    # Initialize the repository.
    cmd = ['git', 'init', repo_root]
    subprocess.check_call(cmd)

    # Import the fast-import string into the repo.
    p = subprocess.Popen(['git', '-C', repo_root, 'fast-import'], stdin=subprocess.PIPE)
    p.communicate(input=import_str)

def applyfilter(blob_filter_fun, file_name, blob, data_idx, progress):
    # Print progress.
    print '\rProgress: %.1f%%' % (progress),
    sys.stdout.flush()

    # Filter the blob and return the result.
    blob = blob_filter_fun(file_name, blob)
    return { 'data_idx': data_idx, 'blob': blob }

# Filter all blobs.
def filterblobs(src_repo, dst_repo, name_filter_fun, blob_filter_fun):
    # Export the source repository.
    print 'Exporting the source repository (' + src_repo + ')...'
    commands = exportrepo(src_repo)

    # Filter all the data blobs.
    print 'Filtering blobs...'

    # Get a list of filter jobs to perform.
    mark_to_blob_data_map = {}
    jobs_map = {}
    for i in xrange(0, len(commands)):
        cmd = commands[i]
        if cmd == 'blob':
            # data blob
            mark = commands[i + 1][5:]
            assert(mark[0] == ':')
            data_idx = i + 2
            assert(commands[data_idx][:4] == 'data')
            assert(not (mark in mark_to_blob_data_map))
            mark_to_blob_data_map[mark] = data_idx
        elif cmd[:2] == 'M ':
            # filemodify
            # Get the file name for this file.
            parts = cmd.split(' ')
            file_name = ' '.join(parts[3:])
            if name_filter_fun(file_name):
                # Append this file to the jobs.
                mark = parts[2]
                assert(mark[0] == ':')
                assert(mark in mark_to_blob_data_map)
                data_idx = mark_to_blob_data_map[mark]
                assert(commands[data_idx][:4] == 'data')
                if not (data_idx in jobs_map):
                    jobs_map[data_idx] = file_name

    # Perform all the jobs in parallel using a thread pool.
    pool = multiprocessing.Pool()
    results = []
    count = 0
    total_count = len(jobs_map)
    for data_idx in jobs_map:
        # Get the file name for this job.
        file_name = jobs_map[data_idx]

        # Extract the blob data from the command list (will be replaced later).
        cmd = commands[data_idx]
        assert(cmd[:4] == 'data')
        nl_idx = cmd.find('\n')
        assert(nl_idx > 0)
        blob = cmd[(nl_idx + 1):]
        commands[data_idx] = '' # Save some memory.

        # Increment progress...
        count += 1
        progress = (100.0 * count) / float(total_count)

        # Perform the filter.
        results.append(pool.apply_async(applyfilter, [blob_filter_fun, file_name, blob, data_idx, progress]))

    # Wait for all jobs in the thread pool to be finished.
    pool.close()
    pool.join()

    # Get the results. Will re-raise any exception raised in worker.
    for result in results:
        res = result.get()
        blob = res['blob']
        data_idx = res['data_idx']

        # Replace the data command using the new blob data.
        commands[data_idx] = 'data ' + str(len(blob)) + '\n' + blob

    # Create the new repository and import the filtered history.
    if os.path.isdir(dst_repo):
        cleandir(dst_repo)
    else:
        os.makedirs(dst_repo)
    print '\nImporting result to ' + os.path.abspath(dst_repo) + '...'
    importtorepo(dst_repo, commands)


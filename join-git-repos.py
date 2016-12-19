#!/usr/bin/python
# -*- mode: Python; tab-width: 4; indent-tabs-mode: nil; -*-
"""
  Copyright (C) 2016 Marcus Geelnard

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

import argparse, os, shutil, subprocess

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

# Parse a repository specification.
def getrepospec(spec):
    # Extract the branch.
    sep = spec.find(':')
    if sep >= 0:
        branch = spec[(sep + 1):]
        spec = spec[:sep]
    else:
        branch = 'master'

    # Extract the name.
    sep = spec.find(',')
    if sep >= 0:
        name = spec[(sep + 1):]
        spec = spec[:sep]
    else:
        name = os.path.basename(os.path.abspath(spec))

    # Extract the path.
    path = spec

    return { 'path': path, 'name': name, 'branch': branch }

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
def importtorepo(repo_root, commands, branch):
    # Generate a string from the export description.
    import_str = makeimport(commands)

    # Initialize the repository.
    cmd = ['git', 'init', repo_root]
    subprocess.check_call(cmd)

    # Import the fast-import string into the repo.
    p = subprocess.Popen(['git', '-C', repo_root, 'fast-import'], stdin=subprocess.PIPE)
    p.communicate(input=import_str)

    # Checkout the tip of the main branch.
    cmd = ['git', '-C', repo_root, 'reset', '--hard', branch]
    subprocess.check_call(cmd)

# Move all files to a subdirectory.
def movetosubdir(commands, subdir):
    if subdir[-1:] != '/':
        subdir += '/'
    for k in xrange(0, len(commands)):
        cmd = commands[k]
        cmd_type = cmd[:2]
        # Commands that reference paths: 'M', 'D', 'C' and 'R'.
        if cmd_type == 'M ':
            parts = cmd.split(' ')
            parts[3] = subdir + parts[3]
            cmd = ' '.join(parts)
            commands[k] = cmd
        elif cmd_type == 'D ':
            parts = cmd.split(' ')
            parts[1] = subdir + parts[1]
            cmd = ' '.join(parts)
            commands[k] = cmd
        elif (cmd_type == 'C ') or (cmd_type == 'R '):
            # Trickery: First path must be quoted in case it contains spaces.
            if cmd[2] == '"':
                src_start = 3
                src_end = cmd.find('"', src_start)
                src_path = '"' + subdir + cmd[src_start:src_end] + '"'
                dst_path = subdir + cmd[(src_end + 1):]
            else:
                src_start = cmd.find(' ') + 1
                src_end = cmd.find(' ', src_start)
                src_path = subdir + cmd[src_start:src_end]
                dst_path = subdir + cmd[(src_end + 1):]
            commands[k] = cmd_type + src_path + ' ' + dst_path

# Get the maximum mark number.
def getmaxmark(commands):
    max_mark = 0
    for cmd in commands:
        if cmd[:5] == 'mark ':
            mark = int(cmd[6:])
            if mark > max_mark:
                max_mark = mark
    return max_mark

# Renumber all marks (add an offset).
def renumbermarks(commands, mark_offset):
    for k in xrange(0, len(commands)):
        cmd = commands[k]

        colon_pos = cmd.find(':')
        if (colon_pos > 0):
            # Handle 'mark', 'from' and 'merge'.
            if cmd[:colon_pos] in ['mark ', 'from ', 'merge ']:
                mark_pos = colon_pos + 1
                mark = int(cmd[mark_pos:]) + mark_offset
                commands[k] = cmd[:mark_pos] + str(mark)

            # Handle 'M'.
            elif cmd[:2] == 'M ':
                parts = cmd.split(' ')
                if parts[2][0] == ':':
                    mark = int(parts[2][1:]) + mark_offset
                    parts[2] = ':' + str(mark)
                    commands[k] = ' '.join(parts)

            # Handle 'N'.
            elif cmd[:2] == 'N ':
                parts = cmd.split(' ')
                if parts[1][0] == ':':
                    mark = int(parts[1][1:]) + mark_offset
                    parts[1] = ':' + str(mark)
                if parts[2][0] == ':':
                    mark = int(parts[2][1:]) + mark_offset
                    parts[2] = ':' + str(mark)
                commands[k] = ' '.join(parts)

# Parse the time stamp from an 'author'/'committer' command.
def extracttimestamp(cmd):
    # The time stamp comes directly after the e-mail address (enclosed in <>).
    gt_pos = cmd.index('> ')
    time_stamp = cmd[(gt_pos + 2):]
    # TODO(m): There must be a native Python way of doing this.
    parts = time_stamp.split(' ')
    t = float(parts[0])
    if len(parts[1]) == 5:
        h = float(parts[1][1:3])
        m = float(parts[1][3:5])
        dt = 60 * (m + 60 * h)
        if parts[1][0] == '+':
            t = t - dt
        else:
            t = t + dt
    return t

# Get the log for a specific branch (first-child traversal).
def getlog(commands, branch, repo_id):
    log = []

    ref_names = ['refs/heads/' + branch, 'refs/heads/origin/' + branch]

    # Walk backwards.
    parent_mark = ''
    for k in reversed(xrange(len(commands))):
        cmd = commands[k]
        if not parent_mark:
            # Find the tip of the branch.
            if (cmd[:6] == 'reset ') and (cmd[6:] in ref_names):
                # Found it! Look if we have a 'from' command.
                cmd2 = commands[k + 1]
                if cmd2[:6] == 'from :':
                    parent_mark = 'mark :' + cmd2[6:]

        # Find the next parent commit.
        elif (cmd[:7] == 'commit ') and (commands[k + 1] == parent_mark):
            cmd2_idx = k + 2
            # 'author' (optional) comes after 'mark'.
            if commands[cmd2_idx][:7] == 'author ':
                cmd2_idx = cmd2_idx + 1
            # 'committer' (required) comes after 'author'.
            time_stamp = extracttimestamp(commands[cmd2_idx])
            cmd2_idx = cmd2_idx + 2

            log.append({ 'mark': commands[k + 1], 'time': time_stamp, 'id': repo_id })

            # 'from' (optional) comes after 'committer' and 'data'.
            if commands[cmd2_idx][:5] == 'from ':
                parent_mark = 'mark ' + commands[cmd2_idx][5:]
            else:
                # End of log (no more parents)
                break

    # Return the reversed log (oldest commit first).
    return log[::-1]

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
        if log1[idx1]['time'] < log2[idx2]['time']:
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

# Rename all refs.
def renamerefs(commands, suffix):
    for k in xrange(0, len(commands)):
        cmd = commands[k]

        space_pos = cmd.find(' ')
        if (space_pos > 0):
            # Handle 'commit', 'reset' and 'tag'.
            if cmd[:space_pos] in ['commit', 'reset', 'tag']:
                commands[k] = cmd + suffix

# Remap parent commit marks.
def remapmark(cmd, mark_map):
    # Remap any 'from' commands according to the mark_map.
    colon_pos = cmd.find(':')
    if (colon_pos > 0) and (cmd[:colon_pos] == 'from '):
        mark = cmd[colon_pos:]
        if mark in mark_map:
            cmd = cmd[:colon_pos] + mark_map[mark]
    return cmd

# Merge two repositories.
def mergerpos(main_commands, secondary_commands, main_spec, secondary_spec):
    # Renumber the marks in the secondary command set.
    renumbermarks(secondary_commands, getmaxmark(main_commands))

    # Get a log of the main branch in the main command set.
    main_log = getlog(main_commands, main_spec['branch'], 0)

    # Get a log of the main branch in the secondary command set.
    # NOTE: This has to be done before all the refs are renamed.
    secondary_log = getlog(secondary_commands, secondary_spec['branch'], 1)

    # Sort the logs into a unified log.
    combined_log = combinelogs(main_log, secondary_log)

    # Rename all refs in the secondary command set.
    renamerefs(secondary_commands, '-' + secondary_spec['name'])

    # Combine both repos into a single command sequence.
    commands = []
    sources = [{ 'idx': 0, 'commands': main_commands },
               { 'idx': 0, 'commands': secondary_commands }]
    log_idx = 0
    mark_map = {}
    last_branch_id = -1
    mark_before_break = ''
    mark_from_prev_branch = ''
    while not ((sources[0]['idx'] >= len(sources[0]['commands'])) and (sources[1]['idx'] >= len(sources[1]['commands']))):
        # Pick the next branch and merge point from the log.
        log_done = (log_idx >= len(combined_log))
        if not log_done:
            current_branch_id = combined_log[log_idx]['id']
            next_mark = combined_log[log_idx]['mark']
            log_idx = log_idx + 1
        else:
            current_branch_id = 0 if sources[0]['idx'] < len(sources[0]['commands']) else 1

        # If we switched branches, update the mark map.
        if mark_before_break and (last_branch_id != current_branch_id) and (last_branch_id >= 0):
            if mark_from_prev_branch:
                mark_map[mark_from_prev_branch] = mark_before_break
            mark_from_prev_branch = mark_before_break

        # Iterate the selected branch until we hit the merge point from the log.
        source = sources[current_branch_id]
        src_commands = source['commands']
        processed_all_commands = True
        first_commit_of_branch = (source['idx'] == 0)
        mark_before_break = ''
        for k in xrange(source['idx'], len(src_commands)):
            if (not log_done) and (src_commands[k] == next_mark):
                # Sanity check: The previous command must be a 'commit'.
                if src_commands[k - 1][:7] != 'commit ':
                    raise ValueError('Missing a commit command.')

                # Special handling of the first commit of the branch: Make sure
                # that it is attached to the other branch (if any), or the other
                # branch will be orphaned.
                new_parent_cmd = ''
                if first_commit_of_branch and mark_from_prev_branch:
                    new_parent_cmd = 'from ' + mark_from_prev_branch
                first_commit_of_branch = False

                # Finish this commit.
                for i in xrange(k, len(src_commands)):
                    cmd = src_commands[i]
                    space_pos = cmd.find(' ')
                    cmd_type = cmd[:space_pos] if space_pos > 0 else cmd
                    if not (cmd_type in ['mark', 'author', 'committer', 'data', 'from', 'merge', 'M', 'D', 'C', 'R', 'deleteall', 'N']):
                        source['idx'] = i
                        processed_all_commands = False
                        break
                    else:
                        commands.append(remapmark(cmd, mark_map))
                        if new_parent_cmd:
                            if cmd_type == 'data':
                                commands.append(new_parent_cmd)
                            elif cmd_type == 'from':
                                # Sanity check: There should be no 'from' here.
                                raise ValueError('Unexpected from command.')

                # Remember which mark caused us to break from the command stream.
                mark_before_break = next_mark[5:]

                break
            else:
                # Append the command to the command queue, with parent remapping.
                commands.append(remapmark(src_commands[k], mark_map))

        if processed_all_commands:
            source['idx'] = len(src_commands)

        last_branch_id = current_branch_id

    return commands

# Handle the program arguments.
parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description='Generate a new repository with stiched histories from two or more repositories.',
    epilog=('A repository specification is given on the following format:\n' +
           '  path[,name][:mainbranch]\n' +
           '    path       - Root of the Git repository.\n' +
           '    name       - Name of the repository (used for the subdir).\n' +
           '                 (default: last part of the path)\n' +
           '    mainbranch - The main branch of the repository.\n' +
           '                 (default: master)\n'))
parser.add_argument('-n', '--no-subdirs', action='store_true', help='do not create subdirectories')
parser.add_argument('-o', '--output', metavar='OUTPUT', required='True', help='output directory for the stiched Git repo')
parser.add_argument('main', metavar='MAIN', help='main repository specification')
parser.add_argument('secondary', metavar='SECONDARY', nargs='+', help='secondary repository specification')
args = parser.parse_args()

# Should we append subdirs?
move_to_subdirs = not args.no_subdirs

# Export the main repository.
main_spec = getrepospec(args.main)
print 'Exporting the main repository (' + main_spec['name'] + ')...'
main_commands = exportrepo(main_spec['path'])
if move_to_subdirs:
    movetosubdir(main_commands, main_spec['name'])

# For each secondary repository...
for secondary in args.secondary:
    secondary_spec = getrepospec(secondary)
    print '\nExporting ' + secondary_spec['name'] + '...'
    secondary_commands = exportrepo(secondary_spec['path'])
    if move_to_subdirs:
        movetosubdir(secondary_commands, secondary_spec['name'])

    print '\nMerging repositories...'
    main_commands = mergerpos(main_commands, secondary_commands, main_spec, secondary_spec)

# Create the new repository and import the stiched histories.
out_root = args.output
if os.path.isdir(out_root):
    cleandir(out_root)
else:
    os.makedirs(out_root)
print '\nImporting result to ' + os.path.abspath(out_root) + '...'
importtorepo(out_root, main_commands, main_spec['branch'])


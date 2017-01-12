# git-tools

This is a collection of useful tools for Git.

## join-git-repos

The purpose of `join-git-repos` is to combine several Git repositories into a
single repository. It will do the following:

  * Import the complete history (including tags and branches) of two or more
    repositories into a new, single repository.
  * Move each source repository into a dedicated sub-folder in the new
    repository, for *all* commits in the history (this guarantees that there
    are no merge conflicts).
  * Stitch the histories of the *main* branches (e.g. master) of all source
    repositories, in commit date order, while preserving branch and merge points
    (this makes it possible to check out an old commit and the result should be
    a reasonable representation of all the source repositories at the given
    time in history).
  * Rename all the refs (branches and tags) in all source repositories except
    the first (main) repository. For instance, when joining the repositories
    `foo`  and `bar`, there will be two branches called `master` and
    `master-bar` in the resulting repository. This minimizes the risk of name
    collisions.

## git-filter-blobs

This tool allows you to modify blobs (file content) for all versions of all
files in a repository. The result is written to a new repository that is a
complete clone of the source repository (except that file content may have
changed).

For example, to run `clang-format` on all C/C++ files in the history (making it
appear as if the files have been correctly formatted from the beginning), you
can run:

```bash
git-filter-blobs.py -f h,hpp,c,cpp path/to/old-repo path/to/new-repo 'clang-format -style="{BasedOnStyle: Chromium, ColumnLimit: 100}"'
```

Note that if the command string includes `%f`, it will be expanded to the
filename of the blob that is being processed. That can be useful for creating
more advanced file filters (e.g. to filter based on the folder in which the
file is located), or to select different tools for different file types,
for instance.


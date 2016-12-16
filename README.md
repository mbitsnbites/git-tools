# git-tools

This is a collection of useful tools for Git.

## join-git-repos

The purpos of `join-git-repos` is to combine several Git repositories into a
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


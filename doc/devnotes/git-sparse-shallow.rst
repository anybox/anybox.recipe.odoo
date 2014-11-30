Git shallow clones and selective branch fetching
================================================

Behavior on shallow clones
--------------------------

* ``git fetch --depth`` will remove prior revision whereas
  ``git clone --depth`` followed by normal fetch will just start with
  a shallow clone and stack new commits on top of that.
  Therefore fetch --depth looks to be potentially
  destructive although first tests with a local commit seem to be satisfactory.

  Let's face it, people will be mostly interested in the huge gain of
  not having the pile of old history.

* ``git fetch`` cannot specify a precise revision by SHA1, nor can ``git clone``

  From the `Git mailing list <http://thread.gmane.org/gmane.comp.version-control.git/115811>`_:

     No, out of security concerns; imagine you included some proprietary source code by mistake, and undo the damage by forcing a push with a branch that does not have the incriminating code. Usually you do not control the garbage-collection on the server, yet you still do not want other people to fetch "by SHA-1".

In the recipe
-------------

The current implementation of Git support in the recipe starts with
an inconditional fetch. Then it is assumed, to detect a branch, that
the output of ``git branch`` is useful. This way of doing prevents
any sparse tactics.

We should probably instead:

* detect SHA references, which can't be fetched
* fetch what can be fetched
* use a branch indication to allow for sparse fetch/checkout of a
  precise commit (a very important use-case). Of course, the freeze
  feature should provide that, meaning that the ``revisions`` option
  should also support it.

  In short, in the absence of tags, the best economy we can make to
  fix a revision is to limit to the proper branch.

  Worse, branches are just pointers, they aren't intangible. This means
  that we should have a retry fetching everything in case the branch
  does not exist in remote any more, or does not hold the wished commit.


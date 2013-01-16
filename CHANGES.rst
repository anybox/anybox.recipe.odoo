Changes
~~~~~~~

1.4 (16-01-2013)
----------------

- launchpad #1093771: extraction feature of downloaded code (notably vcs)
- launchpad #1068360: new 'revisions' option to fix VCS revisions separately
- launchpad #1093474: freeze feature of revisions and versions of
  python distributions
- launchpad #1084535: finer behaviour of ``with_devtools`` option:
  load testing hacks only in tests launcher script
- launchpad #1095645: missing devtools loading in openerp-command
  scripts
- launchpad #1096472: forbid standalone (single) local addons. A local
  addon must always be a directory that has addons inside.
- launchpad #1096472: trailing slash in a standalone addon directory name
  led to error.

1.3 (21-11-2012)
----------------

- launchpad #1077048: fix gunicorn startup script for OpenERP 7
- launchpad #1079819: take into account newly introduced hard
  dependency to PIL in OpenERP 7
- launchpad #1055466: refactor version logic by providing major
  version tuple for comparisons.
- launchpad #1081039: introduced soft requirements and made
  openerp-command one of these.

1.2.2 (11-11-2012)
------------------

- Nothing but fix of changelog RST

1.2.1 (08-11-2012)
------------------

- Fixed an error in user feedback if openerp-command package is missing but
  needed

1.2 (07-11-2012)
----------------

- launchpad #1073917: separated test command (bin/test_openerp)
- launchpad #1073127: support for openerp-command
- major improvement of test coverage in server recipe
- included buildout configurations for buildbotting of the recipe in source
  distribution

1.1.5 (14-10-2012)
------------------
- Improved documentation (bootstrap and sample buildouts)
- Re-enabled support for trunk nightly (and maybe 7.0 final)
- fixed a packaging problem with openerp-cron-worker in 1.1.4

1.1.3 (26-09-2012)
------------------
- launchpad #1041231: Resilience to changes of bzr locations
- launchpad #1049519: openerp-cron-worker startup script
- launchpad #1025144: By default, admin passwd is now disabled
- launchpad #1054667: Problem with current dev nightlies for OpenERP 6.2
- fixed a packaging problem with openerp-cron-worker in 1.1.2

1.0.3 (24-08-2012)
------------------
- no actual difference with 1.0 (only changelogs and the like)

1.0 (24-08-2012)
----------------
- launchpad #1040011: works with current OpenERP trunk (future 7.0)
- launchpad #1027994: 'base_url' option, to download from mirrors
- launchpad #1035978: restored 'local' version scheme for OpenERP
  itself. Also implemented the 'url' version scheme.
- removed deprecated renaming of 6.1 to 6.1-1
- Refactored the documentation

0.17 (07-08-2012)
-----------------
- launchpad #1033525: startup_delay option
- launchpad #1019888: Gunicorn integration.
- launchpad #1019886: installation of 'openerp' as a develop distribution, and
  full python server startup script.
- launchpad #1025617: Support for nightly versions in 6.1 series
- launchpad #1025620: Support for latest version
- launchpad #1034124: Fix interference of buildout options with
  gtkclient recipe
- launchpad #1021083: optional development tools loading in startup script
- launchpad #1020967: stop creating scripts by default
- launchpad #1027986: Better handling of interrupted downloads

0.16 (29-06-2012)
-----------------
- launchapd #1017252: relying on Pillow to provide PIL unless PIL is
  explicitely wanted.
- launchpad #1014066: lifted the prerequirement for Babel. Now the recipe
  installs it if needed before inspection of OpenERP's setup.py

0.15 (14-06-2012)
-----------------
- launchpad #1008931: Mercurial pull don't take URL changes into
  account. Now the recipe manages the repo-local hgrc [paths]
  section, updates the default paths while storing earlier values
- launchpad #1012899: Update problems with standalone vcs addons
- launchpad #1005509: Now bzr branches are stacked only if
   ``bzr-stacked-branches`` option is set to ``True``.

0.14.1 (17-05-2012)
-------------------
- launchpad #1000352: fixed a concrete problem in Bzr reraising

0.14 (17-05-2012)
-----------------
- launchpad #1000352: option vcs-clear-retry to retrieve from scratch in case
  of diverged Bzr branches. Raising UpdateError in right place would trigger
  the same for other VCSes.
- Basic tests for Git and Svn
- Refactor with classes of VCS package 

0.13.1 (14-05-2012)
-------------------
- launchpad #997107: fixed vcs-clear-locks option for bzr, that
  requires a user confirmation that cannot be bypassed in older versions

0.13 (14-05-2012)
-----------------
- launchpad #998404: more robust calls to hg and bzr (w/ unit tests),
  and have exception raised if vcs call failed (break early, break
  often).
- launchpad #997107: vcs-clear-locks option (currently interpreted by
  Bzr only)

0.12 (02-05-2012)
-----------------
- launchpad #993362: addons subdir option, and made repositories being
  one addon usable by creating an intermediate directory.

0.11 (18-04-2012)
-----------------

- Faster tarball inspection (see lp issue #984237)
- Shared downloads and more generally configurable downloads
  directory, see https://blueprints.launchpad.net/anybox.recipe.openerp/+spec/shared-downloads

0.10 (02-04-2012)
-----------------

- fixed the sample buildouts in the readme file

0.9 (23-03-2012)
----------------

- Clean-up and refactoring
- Removed `url` option (download url supported through `version`)
- Support OpenERP 6.1 and 6.0
- Added an 'addons' option allowing remote repositories and local directories
- Improved error messages
- Updated the documentation
- Handle bad Babel import in setup.py
- Support offline mode of buildout
- Create gtk client config without starting it

0.8 (20-12-2011)
----------------

- handle deploying custom bzr branches

0.7 (14-09-2011)
----------------

- handle new sections in openerp config

0.6 (11-09-2011)
----------------

 - Overwrite config files each time
 - Make the "dsextras" error more explicit (install PyGObject and PyGTK)
 - fixed some deps
 - improved the doc

0.5 (10-08-2011)
----------------

 - Use dotted notation to add openerp options in the generated configs

0.4 (09-08-2011)
----------------

 - Added support for the web client and gtk client

0.3 (08-08-2011)
----------------

 - fixed config file creation

0.2 (08-08-2011)
----------------

 - Pass the trailing args to the startup script of the server

0.1 (07-08-2011)
----------------

 - Initial implementation for the OpenERP server only

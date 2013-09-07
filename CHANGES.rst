Changes
~~~~~~~

1.7.1 (2013-09-07)
------------------
- launchpad #1215838: don't freeze develop / gp.vcsdevelop distributions
- launchpad #1213469: openerp scripts: support for entry point
  arguments
- launchpad #1215833: preserve regular develops in extract-downloads-to
- launchpad #1215873: [git] re-buildout with revision fixed versions crashes
- launchpad #1217816: [bzr] proper update of lightweight checkouts
- launchpad #1203550: [v8] using the openerpcommand that comes now bundled
  with openobject-server
- launchpad MP #182002: new 'etc-directory' option (default behaviour
  unchanged).
- launchpad #1208028: wrong error message in case of distribution
  version conflict
- launchpad #1216498: fixed python interpreter extra paths
- launchpad #1216835: [bzr] mispelling in 'lightweight-checkout' option
- launchpad #1205063: no more error if no addons are specified (might
  lead to problems with the default config, though, because of server
  wide modules, but that's supposed to be overridable)


1.7.0 (2013-07-26)
------------------
- launchpad #1189160: easy integration of general purpose unit test launchers
- launchpad #1201715: allow easily working in a virtualenv with extra-requires
  on bzr (allows easily to work with zc.buildout 2.2 on systems providing 
  setuptools < 0.7 / distribute) 
- launchpad #1202150: [git] proper support for remote branches
- launchpad #1200449: new flexible ``openerp_scripts``; general refactor of
  script generation code.
- launchpad #1203005: vcs options not passed through (addons and main software)
- [bzr] support for lightweight checkout, with uniform 'bzr-init' option
- launchpad #1204573: [bzr] retry in two steps for some bzr branching
  cases where it fails to branch directly to wished revision.
- launchpad #1128146: new option in ``freeze-to`` to disallow picked
  versions, stopping not freezing of distribute.
- introduced ``vcs.base.CloneError`` with wrappers for ``check_call``
  and ``check_output``.

1.6.4 (2013-07-14)
------------------
- launchpad #1200198: hg: determination whether rev spec is fixed could be wrong
- launchpad #1194887: 'clean' option for git and hg now use the native solution

1.6.3 (2013-06-23)
------------------
- launchpad #1192973: 'clean' option now based on bzr clean-tree (more 
  powerful, and avoids in particular removing empty dirs, which is a local
  modification that prevents later on freezing)

1.6.2 (2013-06-15)
------------------
- launchpad #1189402: order of the addons_path is now deterministic
- launchpad #1189162: registry helping avoid double evaluaton of
  custom addons models (helps launching unittest2 tests directly)
- launchpad #1191279: first implementation of new 'clean' option,
  dealing with python object files only.

1.6.1 (2013-06-06)
------------------
- launchpad #1188402: fixed git clone init on a precise revision

1.6.0 (2013-05-30)
------------------
- launchpad #1183005: python interpreter that can bootstrap OpenERP
  and open a database for interactive session or to launch a script.
- launchpad #1182589: avoid IOError if a bzr branch has no branch.conf
- launchpad #1185097, #1185100, #1185101, #1185741: advanced support
  for Git (precise revision, freeze, extract) allows including Git
  repositories in a full release process for tarball deployments.

1.5.5 (2013-05-20)
------------------
- launchpad #1182146: clearer user feedback and exit status code = 17
  for freeze-to in case of local modifications of VCS server or addons.

1.5.4 (2013-05-14)
------------------
- launchpad #1169124: regression: offline mode not honoured with bzr

1.5.3 (2013-04-11)
------------------
- launchpad #1166788: regression with bzr "revid:" revision specifications

1.5.2 (2013-04-06)
------------------
- launchpad #1154719: freeze-to does not take the correct bzr revision number
- launchpad #1133248: "need more than 1 value to unpack" if some bzr's
  branch.conf has extra content not in the key = value form
- support for bzr stacked branches for the server branch in the same
  way as was already done in addons.
- launchpad #1152808: corrected parsing of options.log_handler in
  gunicorn setups (introduced a constant to treat comma-separated list
  options in gunicorn conf)
- launchpad #1153036: avoid pulls in case the specified revision is
  a fixed one that we already have (bzr and hg only)
- launchpad #1115504: extract-downloads-to now works with bzr version
  shipping with Debian squeeze

1.5.1 (27-02-2013)
------------------

- launchpad #1130590: errors with inline comments such as freeze-to produces

1.5.0 (14-02-2013)
------------------

- works with zc.buildout 2.0
- launchpad #1115503: now it's possible to apply ``extract-downloads-to``
  for a buildout configuration that uses the ``revisions`` option: the
  produced configuration resets ``revisions`` if needed.
- launchpad #1122015: soft requirements problem if offline on zc.buildout 2.0
- quality: now entirely flake8 compliant

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

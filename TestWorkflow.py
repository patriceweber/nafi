
import os
import sys
import argparse
import logging
import datetime

import re
from re import RegexFlag

from shutil import copyfile

from nafi.utils import Globals
from nafi.utils import readConfig
from nafi.utils import LogEngine
from nafi.utils import sanityCheck
from nafi.utils import importClassByName
from nafi.utils import displayRunConfiguration

from nafi.landsat import landsatScene
from nafi.metadata import landsat8Manager

#===============================================================================
#                        Begin parsing command line options
#===============================================================================

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-c', '--config', nargs=1, metavar='filename', default='params.conf', help='Configuration file')
parser.add_argument('-wf', '--workflow', nargs=1, metavar='classname', default='', help='SAGA Workflow classname')
parser.add_argument('-tf', '--tarfile', nargs=1, metavar='filename', default=None, help='Scene TAR file')
parser.add_argument('-d', '--display', help='Displays file naming convention', default=False, action='store_true')
parser.add_argument('-f', '--force', help='Forces run of all workflow computations', default=False, action='store_true')
parser.add_argument('-r', '--revision', help='Displays script version/revision', default=False, action='store_true')
parser.add_argument('-v', '--validate', help='Validates configuration file parameters', default=False, action='store_true')

args = parser.parse_args()

if len(sys.argv) == 1:
    print('\n')
    parser.print_help()
    exit(0)

print(' ')
# ====================================================== args.revision ====

# Print Script version/revision
if args.revision:
    print(' CY_process.py --> version: {0}'.format(Globals.VERSION))
    exit(0)

# Init logging engine
logname = Globals.LOGNAME
engine = LogEngine()
engine.initLogger(name=logname)

# Get logger instance
logger = engine.logger

# =======================================================  args.config ====
#
# Verify the configuration file exists (default or from command line)
if args.config.__class__.__name__ == 'list':
    fconfig = args.config[0]
else:
    fconfig = args.config

basename = os.path.basename(fconfig)

if basename == fconfig:
    # try relative path
    if not os.path.isfile(os.path.join(os.getcwd(), fconfig)):
        logger.critical('Config file not found: %s', os.path.join(os.getcwd(), fconfig))
        exit(1)
else:
    if not os.path.isfile(fconfig):
        logger.critical('Config file not found: %s', fconfig)
        exit(1)

# ======================================================  Config file  =====
# Read configuration file into a dictionary
config = readConfig(fconfig)
if config is None:
    exit(1)

# ======================================================= args.workflow ====
# if workflow class in command line
if args.workflow:
    config['workflow'] = args.workflow[0]


# Update logger engine properties
log_basename = config['workflow'].split('.')[-1]
engine.addFilelogHandler(basename=log_basename, rotations=config['rotations'], timestamp=config['timestamp'], identifier=config['identifier'])

level = logging.DEBUG if config['verbose'] else logging.INFO
engine.setLogLevel(level)

# =======================================================   args.force  ====
# Add 'force' switch value to config
config['force'] = args.force

# ======================================================= args.validate ====
# Do we need to validate the config file?
if args.validate is True:

    level = logging.DEBUG if config['verbose'] else logging.INFO
    logger.setLevel(level)

    _status = sanityCheck(config)
    displayRunConfiguration(config, _status)

    if args.display is True:

        wf_name = config['workflow']
        wf_cls = importClassByName(wf_name)

        if wf_cls is not None:
            wf_cls.fileNamingConvention()
        else:
            logger.critical('SAGA Workflow class name is not valid')

    exit(0)

# ======================================================= args.display ====
# Do we need to display the file naming convention?
if args.display is True:

    wf_name = config['workflow']
    wf_cls = importClassByName(wf_name)

    if wf_cls is not None:
        wf_cls.fileNamingConvention()
    else:
        logger.critical('SAGA Workflow class name is not valid')

    exit(0)

# ======================================================= args.tarfile ====
#
if args.tarfile is None:
    print('\n')
    print('Landsat scene tar file is required (option: -tf')
    parser.print_help()
    exit(0)

else:
    # initialize scene object
    if args.tarfile.__class__.__name__ == 'list':
        archive = args.tarfile[0]
        tarfile = os.path.basename(args.tarfile[0])
    else:
        archive = args.tarfile
        tarfile = os.path.basename(args.tarfile)

    patterns = [r'(^[a-zA-Z0-9]{3})(\d{3})(\d{3})(\d{7})LGN00.tgz$',\
                r'^L([a-zA-Z]{1})([0-9]{2})_([a-zA-Z0-9]{4})_(\d{3})(\d{3})_(\d{8})_(\d{8})_(\d{2})_([a-zA-Z0-9]{2}).tgz$']


    for pattern in patterns:
        re_compile = re.match(pattern, tarfile, RegexFlag.IGNORECASE)
        if re_compile != None:
            break

    if re_compile is None:
        logger.critical('Unknown scene tarfile format')
        exit(1)
    else:
        groups = re_compile.groups()

        if len(groups) == 4:

            sensor = groups[0]
            path = groups[1]
            row = groups[2]

            try:
                strdate = groups[3]
                filedate = datetime.datetime.strptime(strdate, '%Y%j')
                acqdate = filedate.strftime('%Y-%m-%d')

            except ValueError:
                logger.critical('Error parsing date: %s. Required format is [YYYY][MM][DD]', strdate)
                exit(1)

        if len(groups) == 9:

            sensor = groups[0:2]
            path = groups[3]
            row = groups[4]

            try:
                strdate = groups[5]
                filedate = datetime.datetime.strptime(strdate, '%Y%m%d')
                acqdate = filedate.strftime('%Y-%m-%d')

            except ValueError:
                logger.critical('Error parsing date: %s. Required format is [YYYY][MM][DD]', strdate)
                exit(1)

        metadb = landsat8Manager()
        metadata = metadb.getSceneProductIDs(path, row, acqdate, acqdate)

        if len(metadata) == 1:
            scene = landsatScene(metadata[0])
            scene.setTarArchive(tarfile)
        else:
            logger.critical('Error getting metadata, too many entries: array size=%d', len(metadata))
            exit(1)
        # Copy tar file in proper directory structure if not present
        rootdir = config['working_d']
        outpath = os.path.join(rootdir, scene.directory)
        if outpath != os.path.dirname(archive):
            if os.path.exists(outpath) is False:
                os.makedirs(outpath)
            if not os.path.isfile(os.path.join(outpath, tarfile)):
                copyfile(archive, os.path.join(outpath, tarfile))

#===============================================================================
#                        Done parsing command line options
#===============================================================================

#===============================================================================
#                        Execute setup tasks
#===============================================================================

# Log version used
logger.info('Script %s, version: [%s]', os.path.basename(__file__), Globals.VERSION)


# Print out script settings and set logger level
if config['verbose']:
    logger.setLevel(logging.DEBUG)
    displayRunConfiguration(config)
else:
    logger.setLevel(logging.INFO)

# Checks configutation parameters
status = sanityCheck(config)

# Verify that running environment is good.
if len(status):
    displayRunConfiguration(config, status)
    exit(1)

#===============================================================================
#                        Preliminary tasks done.
#===============================================================================

#===============================================================================
#                        Main programme starts here
#===============================================================================

try:

    wf_name = config['workflow']

    wf_class = importClassByName(wf_name)
    if wf_class is None:
        logger.critical('SAGA Workflow class name is not valid')
        exit(1)

    wf = wf_class(config, 'Test_')

    logger.info(' ')
    logger.info('Processing scene:  [%s/%s], acquired on [%s]', scene.path, scene.row, scene.acqdate)

    try:
        wf.processScene(scene)

    except ValueError as error:
        logger.info('Error processing scene: %s', repr(error))

except NameError as error:
    logger.critical('Error workflow class name: %s', repr(error))

except TypeError as error:
    logger.critical('Error creating workflow: %s', repr(error))

exit(0)

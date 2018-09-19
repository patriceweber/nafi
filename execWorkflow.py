
import os
import argparse

import logging
from threading import Thread
from time import sleep

from nafi.utils import Globals
from nafi.utils import LogEngine

from nafi.utils import readConfig
from nafi.utils import sanityCheck

from nafi.utils import importClassByName
from nafi.utils import displayRunConfiguration
from nafi.utils import setDownloadDates

from nafi.landsat import landsatScene
from nafi.downloader import landsatDownloader



def execWorkflow(wkflow_name, config_lk, queue):
    """ Workflow processing main loop
    """

    try:
        wf_class = importClassByName(wkflow_name)

        if wf_class is None:
            logger.critical('SAGA Workflow class name is not valid')
            return

        wf = wf_class(config_lk)

        while True:

            scene = queue.get()

            if scene is not None:
                # Test if we ran into end of scenes marker sensor='XXX'
                if scene.endMarker() == landsatScene.STOP:
                    return
                else:
                    try:
                        wf.processScene(scene)
                    except ValueError as error:
                        logger.info('Error processing scene: %s', repr(error))

                    queue.task_done()

            logger.debug('Listening for new scene to process...')

    except NameError as error:
        logger.critical('Error workflow class name: %s', repr(error))

    except TypeError as error:
        logger.critical('Error creating workflow: %s', repr(error))

    return


#===============================================================================
#                        Begin parsing command line options
#===============================================================================


parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-c', '--config', nargs=1, metavar='filename', default='params.conf', help='Configuration file')
parser.add_argument('-wf', '--workflow', nargs=1, metavar='classname', default='', help='SAGA Workflow classname')
parser.add_argument('-d', '--display', help='Displays file naming convention', default=False, action='store_true')
parser.add_argument('-dt', '--dates', nargs=2, help='Usage: [start_date] [end_date]', default=None)
parser.add_argument('-f', '--force', help='Forces run of all workflow computations', default=False, action='store_true')
parser.add_argument('-r', '--revision', help='Displays script version/revision', default=False, action='store_true')
parser.add_argument('-v', '--validate', help='Validates configuration file parameters', default=False, action='store_true')

args = parser.parse_args()

print(' ')
# ====================================================== args.revision ====
# Print Script version/revision
if args.revision:
    print('\n\tScript \'{0}\', version: {1}\n'.format(os.path.basename(__file__), Globals.VERSION))
    exit(0)

# Init logging engine
logname = Globals.LOGNAME
engine = LogEngine()
engine.initLogger(name=logname)

# Get logger instance
logger = engine.logger
logger.info('\n')

# =======================================================  args.config ====

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
    if args.workflow.__class__.__name__ == 'list':
        config['workflow'] = args.workflow[0]
    else:
        config['workflow'] = args.workflow

# Update logger engine file handler
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


# Checks configutation parameters and verify that running environment is good.
status = sanityCheck(config)
if len(status):
    displayRunConfiguration(config, status)
    exit(1)


# Populate config['dates'] array
setDownloadDates(config, args.dates)

#===============================================================================
#                        Preliminary tasks done.
#===============================================================================

#===============================================================================
#                        Main programme starts here
#===============================================================================

downloader = landsatDownloader(config)
producer = Thread(target=downloader.startDownloads, name='Downloader')
producer.start()
sleep(1)

q_fifo = downloader.getTasksQueue()

workflowName = config['workflow']
execWorkflow(workflowName, config, q_fifo)

logger.info('Done processing all scenes with execWorkflow')

exit(0)

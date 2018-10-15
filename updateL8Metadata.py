
import os
import sys
import time
import logging
import datetime
import argparse
   
from nafi.utils import LogEngine
from nafi.utils import Globals

from nafi.metadata import metaParser
from nafi.metadata import metadataException

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-v', '--version', help='Displays all module versions', default=False, action='store_true')
parser.add_argument('--debug', '--debug', help='Run script in debug mode', default=False, action='store_true')
args = parser.parse_args()


logname = 'L8_Meta'
level = logging.INFO
basedir = Globals.METADATA_LC8_LOG_BASEDIR

# Get log level
if args.debug: 
    level = logging.DEBUG
#   delete existing log file
    logfile = os.path.join(os.path.expanduser(basedir), 'L8_Meta_db.log')
    if os.path.isfile(logfile):
        os.remove(logfile)
              
                  
# Init logging engine
engine = LogEngine()
engine.initLogger(name=logname, location=basedir)
engine.addFilelogHandler(basename='L8_Meta_db')
engine.setLogLevel(level)


# Get logger instance
logger = engine.logger
logger.info('Python interpreter: {0}'.format(sys.version))
logger.info(' ')
logger.info('Date: %s', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
logger.info('Version: {0}'.format(Globals.VERSION))
logger.info('Log level: {0}'.format(logging.getLevelName(level)))
logger.info(' ')

exit(1)

try:

    st = time.time()

    parser = metaParser()
    
    L8_csv = ""
    
    if level == logging.INFO:
        L8_csv = parser.downloadL8Meta()
    
    else:
        rootdir = os.path.expanduser(Globals.METADATA_LC8_BASEDIR)
        L8_csv = os.path.join(rootdir, 'LANDSAT_8_C1.csv')
        
        if not os.path.isfile(L8_csv):
            L8_csv = parser.downloadL8Meta()
    
    
    parser.loadL8Metadata(L8_csv)
    elapsed = time.time() -st

    logger.info('Running time: %.1fs' % elapsed)
    logger.info('Done parsing metadata...')


except metadataException as error:
    logger.critical(repr(error))


exit(0)

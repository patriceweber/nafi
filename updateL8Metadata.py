
import time
import logging
import datetime

from nafi.utils import LogEngine
from nafi.utils import Globals

from nafi.metadata import metaParser
from nafi.metadata import metadataException


# Init logging engine
logname = 'L8_Meta'
basedir = Globals.METADATA_LC8_LOG_BASEDIR

engine = LogEngine()
engine.initLogger(name=logname, location=basedir)
engine.addFilelogHandler(basename='L8_Meta_db')

level = logging.INFO
engine.setLogLevel(level)

# Get logger instance
logger = engine.logger
logger.info(' ')
logger.info('Date: %s', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


try:

    st = time.time()

    parser = metaParser()
    L8_csv = parser.downloadL8Meta()
    parser.loadL8Metadata(L8_csv)

    elapsed = time.time() -st

    logger.info('Running time: %.1fs' % elapsed)
    logger.info('Done parsing metadata...')

except metadataException as error:
    logger.critical(repr(error))


exit(0)


import os, sys, string
import ctypes, platform, itertools

import configparser
from configparser import NoOptionError

from collections import defaultdict

import time, datetime, logging

import re
from re import RegexFlag

import tarfile
from tabulate import tabulate

import socket
from http.client import HTTPConnection, HTTPException, InvalidURL

from robobrowser import RoboBrowser as rb



class Globals():
    """ Class holding global constants used and shared throughout the scripts
    """

    LOGNAME = r'LC8_script'
    VERSION = r'1.0.0 beta'

    # The '~' means home directory. In the case of Windows operating systems
    # it will be C:\Users\USER_HOMEDIR

    METADATA_LC8_BASEDIR = r'~\Documents\nafi\metadata\LC8'
    METADATA_LC8_LOG_BASEDIR = r'~\Documents\nafi\metadata\LC8\logs'

    DOWNLOADER_BASEDIR = r'~\Documents\nafi\downloader'

    WORKFLOWS_BASEDIR = r'~\Documents\nafi\workflows'
    WORKFLOWS_LOG_BASEDIR = r'~\Documents\nafi\workflows\logs'

    # Enable 'benchmark' decorator function
    ALLOW_BENCHMARK = True

    # Constants
    MBYTES = 1024 * 1024


#===============================================================================
# Initialized the script logging engine with two logging handlers: stdout and
# logfile. The script keeps 10 consecutive log files. When the maximum number
# is reached (as defined by 'MAX_ROTATIONS'), the old log files are archived in
# a timestamped tar.gz file.
#===============================================================================

class LogEngine:
    """ Wrapper class for standard output and file logging. The class implements the singleton pattern
        with the inner class '__logger'
    """
    class __logger:


        def __init__(self):

            self.loggername = None
            self.level = None
            self.rootdir = ''
            self.max_rotations = 0

            return

        def initLogger(self, name='', location='', level=logging.DEBUG):

            # Init member variables
            self.loggername = name
            self.rootdir = location
            self.level = level

            # Init logging engine
            _log = logging.getLogger(self.loggername)
            _log.setLevel(self.level)
            logformat = logging.Formatter('%(asctime)s: %(threadName)s: [%(levelname)s]: %(message)s', datefmt='%d/%m/%Y %I:%M:%S %p')

            # Add console ouput handler
            console = logging.StreamHandler(sys.stdout)
            console.setFormatter(logformat)
            _log.addHandler(console)

            # register logging instance as an inner class attribute
            self.__dict__['logger'] = _log

            _log.info('Logger [%s] initialized', self.loggername)

            return

        def setLogLevel(self, level):
            """ Set the logging level (DEBUG, INFO, WARNING etc..)
            """

            self.level = level
            self.__dict__['logger'].setLevel(self.level)

            return

        def addFilelogHandler(self, basename='L8_Script', timestamp=False, rotations=0, identifier=''):

            # Create the directory where log files are saved
            if not self.rootdir:
                logpath = os.path.join(os.getcwd(), 'logs')
            else:
                # Put all the logfiles into a 'rootdir' directory
                if self.rootdir[0] == '~':
                    logpath = os.path.expanduser(self.rootdir)
                else:
                    logpath = os.path.join('', self.rootdir)

            self.rootdir = logpath
            if os.path.exists(logpath) is False:
                os.makedirs(logpath)

            # Set rotating logfile max index
            self.max_rotations = rotations

            # Calculate increment
            index = self.indexIncrement(basename)

            # Add logfile handler
            if  self.max_rotations > 0:

                if timestamp is True:
                    today = datetime.datetime.now().strftime('%Y%m%d-%H%M')
                    if not identifier:
                        logfilename = os.path.join(logpath, '{0}_{1}_{2}.log'.format(basename, today, index))
                    else:
                        logfilename = os.path.join(logpath, '{0}_{1}_{2}_{3}.log'.format(basename, identifier, today, index))
                else:
                    if not identifier:
                        logfilename = os.path.join(logpath, '{0}_{1}.log'.format(basename, index))
                    else:
                        logfilename = os.path.join(logpath, '{0}_{1}_{2}.log'.format(basename, identifier, index))

            else:
                if timestamp is True:
                    today = datetime.datetime.now().strftime('%Y%m%d-%H%M')
                    if not identifier:
                        logfilename = os.path.join(logpath, '{0}_{1}.log'.format(basename, today))
                    else:
                        logfilename = os.path.join(logpath, '{0}_{1}_{2}.log'.format(basename, identifier, today))
                else:
                    if not identifier:
                        logfilename = os.path.join(logpath, '{0}.log'.format(basename))
                    else:
                        logfilename = os.path.join(logpath, '{0}_{1}.log'.format(basename, identifier))


            logfile = logging.FileHandler(logfilename, 'a')
            logformat = logging.Formatter('%(asctime)s: %(threadName)s: [%(levelname)s]: %(message)s', datefmt='%d/%m/%Y %I:%M:%S %p')
            logfile.setFormatter(logformat)

            _log = logging.getLogger(self.loggername)
            _log.addHandler(logfile)

            return

        def indexIncrement(self, basename):

            # Create incremental log filename, MAX_ROTATIONS files
            index = 1
            pattern = r'^{0}_(.+)_([0-9]+)\.log'.format(basename)
            filelogs = [f for f in os.listdir(self.rootdir) if re.match(pattern, f, RegexFlag.IGNORECASE)]
            fnumbers = [re.match(pattern, f, RegexFlag.IGNORECASE).group(2) for f in filelogs]

            try:
                if len(fnumbers) > 0:
                    filelogs.sort(key=natural_keys)
                    fnumbers.sort(key=natural_keys, reverse=True)
                    index = (1 + int(fnumbers[0])) % (1 + self.max_rotations)

                    if index == 0:  # Let start over

                        # Compress old log files before deleted them
                        today = datetime.datetime.now().strftime('%Y%m%d')
                        archive = os.path.join(self.rootdir, '{0}_logs_{1}.tar.gz'.format(self.loggername, today))

                        with tarfile.open(archive, 'w:gz') as tarlogs:
                            for flog in filelogs:
                                tarlogs.add(os.path.join(self.rootdir, flog), flog)

                        # Delete log files
                        [os.remove(os.path.join(self.rootdir, x)) for x in filelogs]
                        index += 1  # no zero index 'cy_process0.log'

            except ValueError as error:
                print('Error in initLogger(): %s', error.args)
                exit(1)

            return index


    # storage for the instance reference
    __instance = None

    def __init__(self):
        """ Create __logger singleton instance """
        if LogEngine.__instance is None:
            LogEngine.__instance = LogEngine.__logger()

    def __setattr__(self, attr, value):
        """ Delegate attribute access to __logger implementation """
        return setattr(self.__instance, attr, value)

    def __getattr__(self, attr):
        """ Delegate attribute access to __logger implementation """
        return getattr(self.__instance, attr)


#################################################################################
#################################################################################

def natural_keys(filename):
    """ Natural sort order helper function """

    def atoi(stext):
        return int(stext) if stext.isdigit() else stext

    return [atoi(c) for c in re.split(r'(\d+)', filename)]


#===============================================================================
#  Read and parse the configuration file. As of now, the file
#  name is hard coded to 'params.conf'. It should be moved to
#  a command line option a la -conf=file_absolute_path
#===============================================================================

def readConfig(f_config):
    """ Configuration helper function. The configuration file key/value
        pairs are read and stored in the 'config' dictionary """

    _key = ''
    logger = LogEngine().logger

    try:
        _config = configparser.SafeConfigParser()
        f_conf = os.path.join(os.getcwd(), f_config)
        _config.read_file(open(f_conf))

        config_lk = {}

        # Load [USGS] section parameters
        _key = '[USGS]: username'
        config_lk['username'] = _config.get('USGS', 'username')

        _key = '[USGS]: password'
        config_lk['password'] = _config.get('USGS', 'password')

        _key = '[USGS]: url_login'
        config_lk['url_login'] = _config.get('USGS', 'url_login')

        _key = '[USGS]: login_timer'
        config_lk['login_timer'] = 60 * _config.getint('USGS', 'login_timer')


        # Load [ENV] section parameters
        _key = '[ENV]: workflow'
        config_lk['workflow'] = _config.get('ENV', 'workflow')

        _key = '[ENV]: timedelta'
        config_lk['timedelta'] = _config.get('ENV', 'timedelta')

        _key = '[ENV]: knowndate'
        config_lk['knowndate'] = _config.get('ENV', 'knowndate')

        _key = '[ENV]: working_d'
        config_lk['working_d'] = _config.get('ENV', 'working_d')

        _key = '[ENV]: verbose'
        config_lk['verbose'] = _config.getboolean('ENV', 'verbose')

        _key = '[ENV]: online'
        config_lk['online'] = _config.getboolean('ENV', 'online')

        _key = '[ENV]: cleanup'
        config_lk['cleanup'] = _config.getboolean('ENV', 'cleanup')

        _key = '[ENV]: cleanup-exclude'
        exclusions = _config.get('ENV', 'cleanup-exclude').replace(' ', '')
        if not exclusions:
            config_lk['cleanup-exclude'] = []
        else:
            config_lk['cleanup-exclude'] = exclusions.split(',')


        # Load [SAGA] section parameters
        _key = '[SAGA]: saga_cmd'
        config_lk['saga_cmd'] = _config.get('SAGA', 'binary')

        _key = '[SAGA]: saga_verbose'
        config_lk['saga_verbose'] = _config.getboolean('SAGA', 'verbose')

        _key = '[SAGA]: saga_cores'
        config_lk['saga_cores'] = _config.getint('SAGA', 'cores')


        # Load [LOGGER] section parameters
        _key = '[LOGGER]: timestamp'
        config_lk['timestamp'] = _config.getboolean('LOGGER', 'timestamp')

        _key = '[LOGGER]: rotations'
        if not _config.get('LOGGER', 'rotations'):
            config_lk['rotations'] = 0
        else:
            config_lk['rotations'] = _config.getint('LOGGER', 'rotations')

        _key = '[LOGGER]: identifier'
        config_lk['identifier'] = _config.get('LOGGER', 'identifier')


        # Load [SCENES] section parameters
        paths = _config.items('SCENES')

        _all_scenes = []

        for entry in paths:

            name = entry[0]
            if re.match(r'^track(\d+)$', name, RegexFlag.IGNORECASE):

                scenes = entry[1]
                # remove whitespaces and split according to [PATHs]/[ROWs]
                pathrows = scenes.replace(' ', '').split(':')

                if pathrows[0]: # skip empy paths
                    paths = pathrows[0].split(',')

                    for path in paths:
                        # a track is a dictionary in the form of {path: [row1], [row2],...}
                        track = defaultdict(list)

                        for row in pathrows[1].split(','):
                            track[path].append(row)

                        _all_scenes.append(track)


        config_lk['scenes'] = _all_scenes

        config_lk['cc_land'] = _config.get('SCENES', 'cc_land')
        if not config_lk['cc_land']:
            config_lk['cc_land'] = 100.0
        else:
            config_lk['cc_land'] = float(config_lk['cc_land'])


        if config_lk['verbose']:
            logger = logging.getLogger(Globals.LOGNAME)
            logger.info('Configuration parsed correctly.')

    except  IOError as error:
        config_lk = None
        logger.critical('Error reading config file --> %s', error.args)

    except  NoOptionError as error:
        config_lk = None
        logger.critical('Error reading config file --> %s', error.args)

    except ValueError as error:
        config_lk = None
        logger.critical('Error reading config file: %s --> %s', _key, error.args)

    return config_lk


#===============================================================================
# Display the run configuration, parsed from the configuration file.
# This function is called when the _DEBUG_ switch is set to 'True'
# or with the script '-h' option
#===============================================================================

def displayRunConfiguration(config_lk, _status=None):
    """ Summarize the configuration environment and highlight invalid
        settings after a call to the 'sanityChecks' helper function """

    if _status is None:
        _status = dict()

    data_matrix = []

    print('\n\n')
    try:
        # [USGS]
        trow = []
        trow.append('[USGS]')
        trow.append('              ')
        data_matrix.append(trow)

        trow = []
        trow.append('USGS Username')
        trow.append(config_lk['username'])
        if 'username' in _status: trow.append(_status['username'])
        data_matrix.append(trow)

        trow = []
        trow.append('USGS Password')
        trow.append(config_lk['password'])
        if 'password' in _status: trow.append(_status['password'])
        data_matrix.append(trow)

        trow = []
        trow.append('USGS Portal')
        trow.append(config_lk['url_login'])
        if 'url_login' in _status: trow.append(_status['url_login'])
        data_matrix.append(trow)

        #[SCENES]
        if 'scenes' in _status:

            trow = []
            trow.append('[SCENES]')
            trow.append('              ')
            data_matrix.append(trow)

            for scene in _status['scenes']:

                trow = []
                mesg = scene.split(':')
                trow.append(mesg[0])
                trow.append(mesg[1])
                trow.append('Out of bound error')
                data_matrix.append(trow)


        # [ENV]
        trow = []
        trow.append('[ENV]')
        trow.append('              ')
        data_matrix.append(trow)

        trow = []
        trow.append('Download date offset in days (timedelta)')
        trow.append(config_lk['timedelta'])
        data_matrix.append(trow)

        trow = []
        trow.append('Download fixed date (knowndate)')
        trow.append(config_lk['knowndate'])
        data_matrix.append(trow)

        trow = []
        trow.append('Script Working directory')
        trow.append(config_lk['working_d'])
        if 'working_d' in _status: trow.append(_status['working_d'])
        data_matrix.append(trow)

        trow = []
        trow.append('Verbose mode (on/off)')
        trow.append(config_lk['verbose'])
        data_matrix.append(trow)

        trow = []
        trow.append('Online mode (on/off)')
        trow.append(config_lk['online'])
        data_matrix.append(trow)

        trow = []
        trow.append('Delete intermediate files (on/off)')
        trow.append(config_lk['cleanup'])
        data_matrix.append(trow)

        trow = []
        trow.append('Exclude from deletion')
        if len(config_lk['cleanup-exclude']) == 0:
            trow.append('None')
        else:
            trow.append(config_lk['cleanup-exclude'])
        data_matrix.append(trow)

        # [SAGA]
        trow = []
        trow.append('[SAGA]')
        trow.append('              ')
        data_matrix.append(trow)

        trow = []
        trow.append('SAGA Commandline')
        trow.append(config_lk['saga_cmd'])
        if 'saga_cmd' in _status: trow.append(_status['saga_cmd'])
        data_matrix.append(trow)

        trow = []
        trow.append('SAGA verbose mode (on/off)')
        trow.append(config_lk['saga_verbose'])
        data_matrix.append(trow)

        trow = []
        trow.append('SAGA CPU cores usage')
        trow.append(config_lk['saga_cores'])
        data_matrix.append(trow)

        trow = []
        trow.append('SAGA Workflow module')
        trow.append(config_lk['workflow'])
        if 'workflow' in _status: trow.append(_status['workflow'])
        data_matrix.append(trow)

        # [LOGGER]
        trow = []
        trow.append('[LOGGER]')
        trow.append('              ')
        data_matrix.append(trow)

        trow = []
        trow.append('Add timestamp to logfile name')
        trow.append(config_lk['timestamp'])
        data_matrix.append(trow)

        trow = []
        trow.append('Maximum number of logfiles before rotation')
        trow.append(config_lk['rotations'])
        data_matrix.append(trow)

        trow = []
        trow.append('Indentifier string')
        trow.append(config_lk['identifier'])
        data_matrix.append(trow)

        print(tabulate(data_matrix, headers=['   Parameter   ', '   Value   ', 'Status'], tablefmt='grid'))
        print(' ')

    except ValueError as error:
        logger = LogEngine().logger
        logger.warning('Error creating file naming convention table: %s', error.args)

    return

def importClassByName(name):
    """ Dynamic module and class loader. Used to instanciate
        the workflow class defined in the configuration file
        or by the command line option (-wf)"""

    logger = LogEngine().logger

    try:
        components = name.split('.')
        mod = __import__(components[0])

        for comp in components[1:]:
            mod = getattr(mod, comp)

    except AttributeError as error:
        logger.critical('Error loading class %s: ', name, repr(error))
        mod = None

    except ModuleNotFoundError as error:
        logger.critical('Error loading class %s: ', name, repr(error))
        mod = None

    return mod

#===============================================================================
# Just to make sure that most configuration parameters are OK
# and the script is good to go. This function could be improved
# with more checks.
#===============================================================================

def sanityCheck(config_lk):
    """ Assert the validity and format of most of the parameters
        defined in the configuration file."""

    HTTPS_PORT = 443
    _status = dict()

#   Validate USGS Landsat8 login url
    if config_lk['online']:
        try:
            url_USGS_login = config_lk['url_login']
            address = url_USGS_login.split('://')
            if address[0] == 'https':
                usgs = HTTPConnection(address[1], HTTPS_PORT)
                usgs.connect()
                usgs.close()
            else:
                raise InvalidURL()

            # Validate USGS account credentials
            _browser = rb(parser='html.parser', history=True)
            url_USGS_login = config_lk['url_login']

            _browser.open(url_USGS_login)
            login = _browser.get_form(action='/login/')
            login['username'] = config_lk['username']
            login['password'] = config_lk['password']
            _browser.session.headers['Referer'] = url_USGS_login

            _browser.submit_form(login)
            # Get browser response page and find if login successful
            rtext = _browser.parsed.text.encode('ascii', 'ignore')
            if re.search('Invalid username/password', str(rtext), flags=RegexFlag.IGNORECASE):
                _status['username'] = 'Invalid Credentials'
                _status['password'] = 'Invalid Credentials'
                print('Invalid username/password')

        except socket.gaierror:
            _status['url_login'] = 'Invalid URL login'
        except InvalidURL:
            _status['url_login'] = 'Invalid URL protocol'
        except HTTPException:
            _status['url_login'] = 'Invalid URL login'


#   Check if Saga commandline programme is accessible
    _saga_cmd = config_lk['saga_cmd']
    if not os.path.isfile(_saga_cmd):
        _status['saga_cmd'] = 'SAGA excecutable not found'

#   Check if workflow classname is valid
    wf_name = config_lk['workflow']
    wf_cls = importClassByName(wf_name)
    if wf_cls is None:
        _status['workflow'] = 'SAGA Workflow is not valid'

#   if on Windows OS, check if working directory drive letter exists
    if 'Windows' in platform.system():
        drive_bitmask = ctypes.cdll.kernel32.GetLogicalDrives()
        drives = list(itertools.compress(string.ascii_uppercase, [ord(x) - ord('0') for x in bin(drive_bitmask)[:1:-1]]))

        _working_dir = config_lk['working_d']

        if _working_dir.split(':')[0] in drives:

            # if working directory doesn't exist, create it
            if os.path.isdir(_working_dir) is False:
                os.makedirs(_working_dir)

        else:
            _status['working_d'] = 'Drive does not exist'

    # ==========================================================
    # Rebuild scene data. Here, we make sure that all path/row
    # data are in range and formatted as a 3 characters long string
    #
    #         path:[1, 233], row: [1,248]
    #
    #         if path = 1 --> '001', row = 68 --> '068'
    # ===========================================================

    _all_scenes = config_lk['scenes']
    _new_scenes = []
    _scene_errors = []

    itrack = 1
    for scenes in _all_scenes:

        try:
            for path in scenes:
                track = defaultdict(list)
                # make sure path is an integer and it's a 3 character padded string
                ipath = int(path) # make sure path is an integer
                if ipath > 233: raise ValueError()
                path = format(ipath, '03d')

                for row in scenes[path]:
                    irow = int(row) # make sure row is an integer
                    if irow > 248: raise ValueError()
                    row = format(irow, '03d')
                    track[path].append(row)

                _new_scenes.append(track)
                itrack += 1

        except ValueError:
            _scene_errors.append('Track #{0}: PATH/ROW {1}/{2}'.format(itrack, path, row))
            itrack += 1


    if len(_scene_errors) > 0:
        _status['scenes'] = _scene_errors

    config_lk['scenes'] = _new_scenes

    logger = LogEngine().logger
    logger.debug('Sanity checks done.')

    return _status


def setDownloadDates(config_lk, dates=None):
    """ Assert proper date formats and store them into the configuration
        dictionary under the key 'dates' """

    all_dates = []
    logger = LogEngine().logger

    if dates is None:

        timedelta = config_lk['timedelta'].replace(' ', '')
        knowndate = config_lk['knowndate'].replace(' ', '')

        if len(timedelta) == 0 and len(knowndate) == 0:
            pass
        else:
            try:
                if  len(timedelta) == 0:
                    text = 'knowndate'
                    if len(knowndate) != 8:
                        raise ValueError()
                    else:
                        all_dates.append(datetime.datetime.strptime(knowndate, '%Y%m%d').strftime('%Y-%m-%d'))
                        logger.info('Using \'knowndate\' option.')
                else:
                    text = 'timedelta'
                    # Calculate LC8 date for download [YYYY][DOY]
                    download_date = datetime.datetime.now() - datetime.timedelta(days=int(timedelta))
                    all_dates.append(download_date.strftime('%Y-%m-%d'))
                    logger.info('Using \'timedelta\' option.')

            except ValueError:
                if text == 'knowndate':
                    logger.critical('Error parsing date [knowndate]=%s. Required format is [YYYY][MM][DD]', knowndate)
                else:
                    logger.critical('Error estimating download date from [timedelta]=%s. Value must be an integer', str(timedelta))

        if len(all_dates) == 0:
            logger.critical('Error estimating the download date')
            exit(1)

    else:
        # We have command line date input
        if len(dates) != 2:
            logger.critical('Option [-dt --date] argument length error: -dt [start_date] [end_date]')
            exit(1)

        else:
            # Check if date format and time increment are correct
            try:
                strdate = dates[0]
                begin = datetime.datetime.strptime(strdate, '%Y%m%d')
                strdate = dates[1]
                end = datetime.datetime.strptime(strdate, '%Y%m%d')

            except ValueError:
                logger.critical('Error parsing date: %s. Required format is [YYYY][MM][DD]', strdate)
                exit(1)

            all_dates.append(datetime.datetime.strptime(dates[0], '%Y%m%d').strftime('%Y-%m-%d'))
            all_dates.append(datetime.datetime.strptime(dates[1], '%Y%m%d').strftime('%Y-%m-%d'))

    config_lk['dates'] = all_dates

    if len(all_dates) > 1:
        logger.info('Processing scene dates from [%s] to [%s]', all_dates[0], all_dates[-1])

    return


def benchmark(func):
    """ Decorator function which can be toggled [on/off] with the switch Globals.ALLOW_BENCHMARK
        The function reports workflow processing steps infomation like:

            - Benchmarked function name, processing step UID, processing step name and
              processing step running time
    """

    if not Globals.ALLOW_BENCHMARK:
        return func

    def report(*args):

        summary = ''
        result = None

        st = time.time()

        if func.__name__ == 'executeSAGATool':

            # Get object reference and important values before command execution
            self = args[0]
            description = args[3]
            puid = self.p_uid

            result = func(*args)
            elapsed = time.time() -st

            # Fill in report
            summary = 'Function name: {0}, '.format(func.__name__)
            summary += 'Process uid: \'{0}, Process name: \'{1}\', '.format(puid, description)
            summary += ('Running time: %.1fs' % elapsed)

        elif func.__name__ == 'createExtractedBandList':

            # Get object reference and important values before command execution
            self = args[0]
            puid = self.p_uid

            result = func(*args)
            elapsed = time.time() -st

            # Fill in report
            summary = 'Function name: {0}, '.format(func.__name__)
            summary += 'Process uid: \'{0}, '.format(puid)
            summary += ('Running time: %.1fs' % elapsed)

        else:

            # Get object reference and important values before command execution
            self = args[0]
            result = func(*args)
            elapsed = time.time() -st

            # Fill in report
            summary = 'Function name: {0}, '.format(func.__name__)
            summary += ('Running time: %.1fs' % elapsed)


        logger = LogEngine().logger
        logger.debug(summary)
        logger.debug(' ')

        return result

    return report

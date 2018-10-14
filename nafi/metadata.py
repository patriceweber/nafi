
import os, sys
import datetime
import logging

import re
from re import RegexFlag
import dateutil.parser as iso8601
import gzip

import sqlite3

from contextlib import contextmanager
from abc import abstractmethod

from robobrowser import RoboBrowser as rb

from nafi.utils import LogEngine
from nafi.utils import benchmark
from nafi.utils import Globals

from nafi.exceptions import metadataException
from nafi.exceptions import MTLParseError

class metadata:
    """ Landsat platforms metadata base class. Holds download URLs, and sensor
        characterisitics and Landsat products naming convention
    """

    baseURL = r'https://earthexplorer.usgs.gov/download/{0}/{1}/STANDARD/EE'
    repositories = {'OLI_TIRS':['4923', '12864'], 'ETM+':['3373', '12267'], 'LT5':['3119', '12266']}

    # Landsat product identification:
    satellites = {'07':'Landsat 7', '08':'Landsat 8'}
    sensors = {'C':'OLI_TIRS', 'O':'OLI', 'E': 'ETM+', 'T':'TM', 'M':'MSS'}
    corrections = {'L1TP':'Precision Terrain', 'L1GT':'Systematic Terrain', 'L1GS':'Systematic'}
    ccategories = {'RT':'Real Time', 'T1':'Tier 1', 'T2':'Tier 2'}

    bandCount = {'OLI_TIRS':11, 'ETM+':8, 'LT5':6}


    def __init__(self):

        self.sensor = None
        self.coll_number = None
        self.coll_type = None
        self.path = None
        self.row = None
        self.acqdate = None
        self.scene_id = None
        self.product_id = None
        self.cc_land = None

        return

    @abstractmethod
    def getSceneURL(self):
        pass

    def getNumberOfBands(self):
        """ Return the number of bands acquired by Landsat sensors
            (OLI/TIRS, ETM+, LT5)
        """

        return metadata.bandCount[self.sensor]

    def decodeProduct(self, filename):
        """ Parse a landstat product filename and extract the relevant information
            according to the U?SGS/Landsat file naming convention:

            https://landsat.usgs.gov/what-are-naming-conventions-landsat-scene-identifiers
        """

        pattern = r'^L([a-zA-Z]{1})([0-9]{2})_([a-zA-Z0-9]{4})_(\d{6})_(\d{8})_(\d{8})_(\d{2})_([a-zA-Z0-9]{2})_B(\d+)\.TIF$'
        re_compile = re.match(pattern, filename, RegexFlag.IGNORECASE)

        if re_compile is not None:

            groups = re_compile.groups()

            if len(groups) == 9:

                attributes = []
                x = metadata.sensors[groups[0]]
                ss = metadata.satellites[groups[1]]
                attributes.append('{0}, sensor: \'{1}\''.format(ss, x))
                caption1 = ' '.join(attributes)

                attributes = []
                llll = metadata.corrections[groups[2]]
                attributes.append('Correction level: \'{0}\','.format(llll))

                date = groups[5]
                attributes.append('Processing date: \'{0}\''.format(date))
                caption2 = ' '.join(attributes)

                attributes = []
                cc = int(groups[6])
                attributes.append('Collection number: \'{0}\','.format(cc))

                tx = metadata.ccategories[groups[7]]
                attributes.append('Collection category: \'{0}\''.format(tx))
                caption3 = ' '.join(attributes)

                #details = ' '.join(attributes)
                title = 'Scene details:'

        return  title, caption1, caption2, caption3


class L8metadata(metadata):
    """ Class holding Landsat8 OLI/TIRS scene metadata.
        Only a selected subset of metadata is used
    """

    def __init__(self, fields):

        # Call base class constructor
        super(L8metadata, self).__init__()

        self.sensor = fields[0]
        self.coll_number = fields[1]
        self.coll_type = fields[2]
        self.path = fields[3]
        self.row = fields[4]
        self.acqdate = fields[5]
        self.scene_id = fields[6]
        self.product_id = fields[7]
        self.cc_land = fields[8]

        return

    def getSceneURL(self):
        """ Returns a Landsat scene download address, based
            on sensor ID and collection tier (i.e. number)
        """

        url = ''

        for sensor in metadata.repositories:
            if sensor == self.sensor:
                ports = metadata.repositories[sensor]
                url = metadata.baseURL.format(ports[self.coll_number], self.scene_id)

        return url

    def __repr__(self):
        return 'Sensor: %s, Path/Row: %s/%s, Acquisition date: %s, Collection: %s, Land cloud cover %.2f' % (self.sensor, self.path, self.row, self.acqdate, self.coll_type, self.cc_land)


class landsat8Manager():
    """ Class responsable for creating the SQLite database and its tables
        and managing all records in landsat8Metadata.db
    """

    def __init__(self):

        self.wfname = r'landsat8Metadata'
        self.rootdir = self.getRootDirectory()
        self.initDatabase()

        return

    def getRootDirectory(self):
        """ Return the directory where the download management database is created.
            By default it will be under '~\Documents\nafi\landsat8\metadata'
        """
        if Globals.METADATA_LC8_BASEDIR[0] == '~':
            return os.path.expanduser(Globals.METADATA_LC8_BASEDIR)
        else:
            return os.path.join('', Globals.METADATA_LC8_BASEDIR)

    @contextmanager
    def getConnection(self):
        """ Manage the connection with the SQLite database and enable
            foreign keys support. The connection is wrapped within a
            context manager generator
        """

        try:
            if os.path.exists(self.rootdir) is False:
                os.makedirs(self.rootdir)
            db_name = os.path.join(self.rootdir, '{0}.db'.format(self.wfname))
            conn = sqlite3.connect(db_name)

            # Enable foreign key support for database
            cur = conn.cursor()
            cur.execute('pragma foreign_keys = on;')

            yield conn

        except Exception as error:
            conn.rollback()
            raise metadataException('Downloader Database Error: {0}'.format(repr(error)))

        else:
            #print('commit transx')
            conn.commit()

        return conn

    def initDatabase(self):

        self.createJournalTable()
        self.createMetadataTable()
        return

    def createJournalTable(self):
        """ Create the main table holding every Landsat8 metadata since 2013
        """

        with self.getConnection() as conn:
            try:
                cur = conn.cursor()
                cur.execute("""\
                                CREATE TABLE IF NOT EXISTS journal_meta
                                (
                                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                                    last_update DATE NOT NULL,
                                    archive_size INTEGER NOT NULL,
                                    all_records INTEGER NOT NULL,
                                    RT_records INTEGER NOT NULL
                            );""")
                cur.close()

            except sqlite3.OperationalError as error:
                cur.close()
                raise metadataException(repr(error))

            except sqlite3.Error:
                cur.close()
                raise metadataException('Error creating table database \'journal_meta\'')
        return

    def createMetadataTable(self):
        """ Create the main table holding every Landsat8 metadata since 2013
        """

        with self.getConnection() as conn:
            try:
                cur = conn.cursor()
                cur.execute("""\
                                CREATE TABLE IF NOT EXISTS scene_meta
                                (
                                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                                    Sensor VARCHAR(10),
                                    Coll_number INTEGER,
                                    Coll_category VARCHAR(2),
                                    Path INTEGER NOT NULL,
                                    Row INTEGER NOT NULL,
                                    acqdate DATE,
                                    Scene_ID VARCHAR(23) NOT NULL,
                                    Product_ID VARCHAR(42),
                                    CC_Full REAL,
                                    CC_Land REAL,
                                    DayNight VARCHAR(6),
                                    UNIQUE(Scene_ID, Product_ID)
                            );""")
                cur.close()

            except sqlite3.OperationalError as error:
                cur.close()
                raise metadataException(repr(error))

            except sqlite3.Error:
                cur.close()
                raise metadataException('Error creating table database \'scene_meta\'')
        return

    def importMetadata(self, bulk_data):
        """ import into 'tmp_meta' table the Landsat 8 metadata
        """

        with self.getConnection() as conn:
            try:
                cur = conn.cursor()
                cur.executemany("""\
                                insert into scene_meta (Sensor, Coll_number, Coll_category, Path, Row, acqdate, Scene_ID , Product_ID, CC_Full, CC_Land, DayNight)
                                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""", bulk_data)

                cur.close()

            except sqlite3.OperationalError as error:
                cur.close()
                raise metadataException(repr(error))

            except sqlite3.Error:
                cur.close()
                raise metadataException('Error importing data into table \'scene_meta\'')
        return

    def getSceneProductIDs(self, path, row, begin_date, end_date, cc_land=100.):

        scenes_meta = []
        
        with self.getConnection() as conn:

            try:
                cur = conn.cursor()
                
#                data = cur.execute("""\
#                                select Sensor, Coll_number, Coll_Category, Path, Row, acqdate, Scene_ID, Product_ID, CC_Land from scene_meta
#                                where Path=? and Row=? and acqdate>=? and acqdate<=? order by acqdate asc;""", (path, row, '2018-02-01', '2018-03-8')).fetchall()
                                
                data = cur.execute("""\
                                select Sensor, Coll_number, Coll_Category, Path, Row, acqdate, Scene_ID, Product_ID, CC_Land from scene_meta
                                where Path=? and Row=? and acqdate>=? and acqdate<=? and CC_Land<=? order by acqdate asc;""", (path, row, begin_date, end_date, cc_land)).fetchall()
                cur.close()

                for fields in data:
                    scenes_meta.append(L8metadata(fields))

            except sqlite3.OperationalError as error:
                cur.close()
                raise metadataException(repr(error))

            except sqlite3.Error as error:
                cur.close()
                message = 'Error accessing table database \'scene_meta\': {0}'.format(repr(error))
                raise metadataException(message)

        return scenes_meta

    def getNumberofRecords(self, category=None):
        """ return number of records filtered by Collection Category
            from 'scene_meta' table the Landsat 8 metadata
        """
        n_records = -1

        with self.getConnection() as conn:
            try:
                cur = conn.cursor()

                if category is None:
                    data = cur.execute('select count() from scene_meta').fetchone()
                else:
                    data = cur.execute('select count() from scene_meta where Coll_Category=?', [category]).fetchone()

                if data.__class__.__name__ == 'tuple':
                    n_records = data[0]

                cur.close()

            except sqlite3.OperationalError as error:
                cur.close()
                raise metadataException(repr(error))

            except sqlite3.Error as error:
                cur.close()
                message = 'Error accessing table database \'scene_meta\': {0}'.format(repr(error))
                raise metadataException(message)

        return n_records

    def updateJournalTable(self, length):
        """ import into 'journal_meta' Landsat 8 metadata last update
        """

        last = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        records = self.getNumberofRecords()
        RTime = self.getNumberofRecords('RT')

        with self.getConnection() as conn:
            try:
                cur = conn.cursor()
                cur.execute("""\
                                insert into journal_meta (last_update, archive_size, all_records, RT_records)
                                values (?, ?, ?, ?);""", (last, length, records, RTime))

                cur.close()

            except sqlite3.OperationalError as error:
                cur.close()
                raise metadataException(repr(error))

            except sqlite3.Error:
                cur.close()
                raise metadataException('Error creating table database \'scene_meta\'')
        return

    def deleteAllRecords(self):
        """ Execute the SQL 'delete from scene_meta'
        """

        with self.getConnection() as conn:
            try:
                cur = conn.cursor()
                cur.execute("delete from scene_meta")

            except sqlite3.Error as error:
                cur.close()
                raise metadataException('Error accessing database: {0}'.format(repr(error)))
        return


class metaParser:

    metafields = ['sensor', 'collection_number', 'collection_category', 'path', 'row', 'acquisitiondate', 'sceneid',\
                  'landsat_product_id', 'cloudcover', 'cloud_cover_land', 'dayornight']
    
    def __init__(self):

        self.records = 0
        self.archive_length = -1
        self.dbase = landsat8Manager()
        self.logger = LogEngine().logger
        
        return

    def getRootDirectory(self):
        """ Return the directory where the download management database
            is created. By default it will be under '~\Documents\nafi\databases'
        """

        documents = os.path.expanduser(r'~\Documents')
        if os.path.exists(documents) is True:
            return os.path.join(documents, 'nafi', 'metadata', 'LC8')

        return

    def gzipfile(self, iname, oname):
        """ Decompress gzipped files (.gz)
        """

        blocksize = 1 << 16     #64kB

        with gzip.open(iname, 'rb') as f_in:

            f_out = open(oname, 'wb')

            while True:
                block = f_in.read(blocksize)
                if not block:
                    break
                f_out.write(block)
            f_out.close()

        return

    def getIndexList(self, headers):
        
        indices = []
        self.logger.debug('=== Entering function \'metaParser.getIndexList(headers)\' ===')
        
        l_headers = list(map(lambda x:x.lower(), headers))
         
        for name in metaParser.metafields:
            
            try:
                index = l_headers.index(name)
                indices.append(index)
                self.logger.debug('Field name [{0}] found at index: {1}'.format(name, index))
            
            except ValueError as error:
                raise metadataException('Error parsing headers, field: \'{0}\' not found'.format(name))
        
        return indices


    @benchmark
    def downloadL8Meta(self):
        """ Download Landsat8 metadata. The metadata are updated daily.

            https://landsat.usgs.gov/download-entire-collection-metadata
        """
        
        self.logger.debug('=== Entering function \'metaParser.downloadL8Meta()\' ===')
        
        fn_csv = ''
        browser = rb(parser='html.parser', history=True)

        try:

            if browser is not None:

                archive = r'LANDSAT_8_C1.csv.gz'
                url = r'https://landsat.usgs.gov/landsat/metadata_service/bulk_metadata_files/{0}'.format(archive)

                response = browser.session.get(url, stream=True)

                # if file exists on USGS server
                if response.status_code == 200:

                    # Get file to download size
                    total_length = int(response.headers.get('content-length'))

                    outpath = self.getRootDirectory()
                    outfile = os.path.join(outpath, archive)
                        
                    with open(outfile, 'wb') as handle:   # the 'with' syntax if part of ContextManager it ensures the file is properly initialized and closed at the end

                        payload = 512
                        sys.stdout.write('\n')
                        mesg1 = '\t\t\tDownloading {0}:'.format(archive)

                        if total_length is None:
                            mesg2 = ' MB'
                        else:
                            f_size = int(total_length/Globals.MBYTES)
                            mesg2 = '/{0} MB'.format(f_size)

                        ichunk = 0
                        size_downloaded = 0
                        self.logger.info('Starting metadata download')

                        for chunk in response.iter_content(chunk_size=payload):
                            if chunk:   # filter out keep-alive new chunks
                                handle.write(chunk)

                                size_downloaded += len(chunk)

                                ichunk += 1
                                if (ichunk % 2000) == 0:
                                    progress = int(ichunk * payload/(1024*1024))
                                    sys.stdout.write('%s: %d%s   \r' % (mesg1, progress, mesg2))
                                    sys.stdout.flush()


                    handle.close()

                    # Download has terminated
                    if os.path.isfile(outfile):

                        self.logger.debug('Size downloaded: [%d] -- Size on server [%d]', size_downloaded, total_length)

                        if size_downloaded == total_length:

                            self.archive_length = total_length

                            # Decompress metadata archive
                            self.logger.info('Decompressing %s', archive)

                            fn_csv = outfile[:-3]

                            try:
                                self.gzipfile(outfile, fn_csv)
                                os.remove(outfile)

                            except (ValueError, OSError, EOFError) as error:
                                raise metadataException(repr(error))

                    else:
                        raise metadataException('Error downloading L8 metadata file: %s', archive)

        except (ValueError, FileNotFoundError) as error:
            raise metadataException('Error downloading L8 metadata file: %s', repr(error))

        return fn_csv

    @benchmark
    def loadL8Metadata(self, f_L8meta):
        """ Read metadata fields from csv file and insert them into the
            database (landsat8Metadata.db)
        """

        self.logger.debug('=== Entering function \'metaParser.loadL8Metadata(f_L8meta)\' ===')
        self.logger.info('Importing Landsat 8 metadata into the database')
        
        self.dbase.deleteAllRecords()
        
        with open(f_L8meta) as fp:

            # read header row and get index list
            headers = fp.readline().split(',')
            indices = self.getIndexList(headers)

            # Input buffer size in bytes
            chunk_size = pow(2, 24)
            ipass = 1
            
            self.logger.debug('File \'{0}\', opened successfully'.format(f_L8meta))
                        
            while True:
                
                idebug = 1
                self.logger.debug('Extracting relevant fields from CSV metadata file')
                self.logger.debug('  ')
                
                lines = fp.readlines(chunk_size)
                if lines:

                    bulk_data = []

                    self.logger.debug('Pass number {0}, {1} lines read'.format(ipass, len(lines)))
                    self.logger.debug('============================')
                    
                    for line in lines:
                        
                        metas = line.split(',')
                        if idebug <= 50:
                            self.logger.debug('\n=== line # {0}'.format(idebug))
                            self.logger.debug(metas)
                            self.logger.debug('---------------------------------------------------------')
                            self.logger.debug(tuple(map(lambda i: metas[i], indices)))
                            idebug += 1
                            
                        bulk_data.append(tuple(map(lambda i: metas[i], indices)))

                    self.logger.debug('\n\n\tImporting Landsat 8 metadata: %d records   \r' % (self.records))
                    
                    self.dbase.importMetadata(bulk_data)
                    sys.stdout.write('\t\t\tImporting Landsat 8 metadata: %d records   \r' % (self.records))
                    sys.stdout.flush()
                    self.records += len(lines)
                    
                    ipass += 1
                
                else:
                    break
            
            self.dbase.updateJournalTable(self.archive_length)
            self.logger.info('{0} records imported into \'scene_meta\''.format(self.records))

        
        if self.logger.level == logging.INFO:
            os.remove(f_L8meta)

        return


class MTLParser:
    """
        Helpers for parsing MTL metadata files used by USGS Landsat and EO-1
        (Hyperion and ALI) Level 1 GeoTIFF scene data archives

        Created by Chris Waigl on 2014-04-20.

        [2014-04-20] Refactoring original landsatutils.py, as MTL file format is
        also used by Hyperion and ALI.

        ----------------------------------------------------------------------------

        Extracted from pygaarst by Frank Warmerdam, original license is:

        The MIT License (MIT)

        Copyright (c) 2013 Chris Waigl

        Permission is hereby granted, free of charge, to any person obtaining a copy of
        this software and associated documentation files (the "Software"), to deal in
        the Software without restriction, including without limitation the rights to
        use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
        the Software, and to permit persons to whom the Software is furnished to do so,
        subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
        FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
        COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
        IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
        CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
    """

# ==================================================================
# = USGS MTL metadata parsing for Landsat, ALI, Hyperion
#
# The metadata file looks like this:
#
# GROUP = L1_METADATA_FILE
#   GROUP = METADATA_FILE_INFO
#     ORIGIN = "Image courtesy of the U.S. Geological Survey"
#     REQUEST_ID = "0501306252996_00005"
#     ...
#     STATION_ID = "LGN"
#     PROCESSING_SOFTWARE_VERSION = "LPGS_2.2.2"
#  END_GROUP = METADATA_FILE_INFO
#  GROUP = PRODUCT_METADATA
#     DATA_TYPE = "L1T"
#     ...
#  END_GROUP = PRODUCT_METADATA
#  END_GROUP = L1_METADATA_FILE
#  END
# ==================================================================


    # Elements from the file format used for parsing
    GRPSTART = r'GROUP = '
    GRPEND = r'END_GROUP = '
    ASSIGNCHAR = r' = '
    FINAL = r'END'

    # A state machine is used to parse the file. There are 5 states (0 to 4):
    STATUSCODE = ['begin', 'enter metadata group', 'add metadata item', 'leave metadata group', 'end']


    def __init__(self):
        self.logger = LogEngine().logger
        return

    # Help functions to identify the current line and extract information
    def _islinetype(self, line, testchar):
        """ Checks for various kinds of line types based on line head
        """
        return line.strip().startswith(testchar)

    def _isassignment(self, line):
        """ Checks if the line is a key-value assignment
        """
        return MTLParser.ASSIGNCHAR in line

    def _isfinal(self, line):
        """ Checks if line finishes a group
        """
        return line.strip() == MTLParser.FINAL

    def _getgroupname(self, line):
        """ Returns group name, if used with group start lines
        """
        return line.strip().split(MTLParser.GRPSTART)[-1]

    def _getendgroupname(self, line):
        """ Returns group name, if used with group end lines
        """
        return line.strip().split(MTLParser.GRPEND)[-1]

    def _getmetadataitem(self, line):
        """ Returns key/value pair for assignment type lines
        """
        return line.strip().split(MTLParser.ASSIGNCHAR)

    # After reading a line, what state we're in depends on the line
    # and the state before reading
    def _checkstatus(self, status, line):
        """ Returns state/status after reading the next line.

        The status codes are::
            0 - BEGIN parsing; 1 - ENTER METADATA GROUP, 2 - READ METADATA LINE,
            3 - END METDADATA GROUP, 4 - END PARSING

        Permitted Transitions:

            0 --> 1, 0 --> 4
            1 --> 1, 1 --> 2, 1 --> 3
            2 --> 2, 2 --> 3
            3 --> 1, 1 --> 3, 3 --> 4

        """

        newstatus = 0

        if status == 0:
            # begin --> enter metadata group OR end
            if self._islinetype(line, MTLParser.GRPSTART):
                newstatus = 1
            elif self._isfinal(line):
                newstatus = 4

        elif status == 1:
            # enter metadata group --> enter metadata group
            # OR add metadata item OR leave metadata group
            if self._islinetype(line, MTLParser.GRPSTART):
                newstatus = 1
            elif self._islinetype(line, MTLParser.GRPEND):
                newstatus = 3
            elif self._isassignment(line):
                # test AFTER start and end, as both are also assignments
                newstatus = 2

        elif status == 2:
            if self._islinetype(line, MTLParser.GRPEND):
                newstatus = 3
            elif self._isassignment(line):
                # test AFTER start and end, as both are also assignments
                newstatus = 2

        elif status == 3:
            if self._islinetype(line, MTLParser.GRPSTART):
                newstatus = 1
            elif self._islinetype(line, MTLParser.GRPEND):
                newstatus = 3
            elif self._isfinal(line):
                newstatus = 4

        if newstatus != 0:
            return newstatus
        elif status != 4:
            err_mesg = 'Cannot parse the following line after status [%s]: (%s)' % (MTLParser.STATUSCODE[status], line)
            raise MTLParseError(err_mesg)

    # Function to execute when reading a line in a given state
    def _transstat(self, status, grouppath, dictpath, line):
        """Executes processing steps when reading a line
        """

        if status == 0:
            err_mesg = 'Status should not be [%s] after reading line: (%s)' % (MTLParser.STATUSCODE[status], line)
            raise MTLParseError(err_mesg)

        elif status == 1:
            currentdict = dictpath[-1]
            currentgroup = self._getgroupname(line)
            grouppath.append(currentgroup)
            currentdict[currentgroup] = {}
            dictpath.append(currentdict[currentgroup])

        elif status == 2:
            currentdict = dictpath[-1]
            newkey, newval = self._getmetadataitem(line)

            # USGS has started quoting the scene center time.  If this
            # happens strip quotes before post processing.
            if newkey == 'SCENE_CENTER_TIME' and newval.startswith('"') \
                    and newval.endswith('"'):
                self.logger.warning('Strip quotes off SCENE_CENTER_TIME.')
                newval = newval[1:-1]

            currentdict[newkey] = self._postprocess(newval)

        elif status == 3:
            oldgroup = self._getendgroupname(line)
            if oldgroup != grouppath[-1]:
                raise MTLParseError(
                    "Reached line '%s' while reading group '%s'."
                    % (line.strip(), grouppath[-1]))
            del grouppath[-1]
            del dictpath[-1]
            try:
                currentgroup = grouppath[-1]
            except IndexError:
                currentgroup = None

        elif status == 4:
            if grouppath:
                raise MTLParseError('Reached end before end of group [%s]' % grouppath[-1])

        return grouppath, dictpath

    # Identifying data type of a metadata item
    def _postprocess(self, valuestr):
        """
        Takes value as str, returns str, int, float, date, datetime, or time
        """

        intpattern = re.compile(r'^\-?\d+$')
        floatpattern = re.compile(r'^\-?\d+\.\d+(E[+-]?\d\d+)?$')
        timepattern = re.compile(r'^\d{2}:\d{2}:\d{2}(\.\d{6})?')

        try:
            if valuestr.startswith('"') and valuestr.endswith('"'):
                # it's a string
                return valuestr[1:-1]

            elif re.match(intpattern, valuestr):
                # it's an integer
                return int(valuestr)

            elif re.match(floatpattern, valuestr):
                # floating point number
                return float(valuestr)

            elif re.match(timepattern, valuestr):
                time = valuestr[0:-2]
                return datetime.datetime.strptime(time, '%H:%M:%S.%f').time()

            else:
            # now let's try the datetime objects
                return iso8601.parse(valuestr)

        except (OverflowError, ValueError) as error:
            print(error)
            pass

        # If we get here, we still haven't returned anything.
        self.logger.info('The value %s couldn\'t be parsed as int, float, or datetime. Returning it as string.' % valuestr)

        return valuestr

    def parse(self, mtl_file):
        """ Parses the metadata.

        Arguments:
            metadataloc: a filename or a directory.
        Returns metadata dictionary, mdata
        """
        if os.path.isfile(mtl_file) is False:
            raise MTLParseError('Metadate file (MTL) not found: %s' % mtl_file)

        filehandle = open(mtl_file, 'rU')

        # Reading file line by line and inserting data into metadata dictionary
        status = 0
        mdata = {}
        grouppath = []
        dictpath = [mdata]

        for line in filehandle:
            if status == 4:
                # we reached the end in the previous iteration,
                # but are still reading lines
                mesg = 'Metadata file %s appears to have extra lines after at the end.' % mtl_file
                self.logger.warning(mesg)

            status = self._checkstatus(status, line)
            grouppath, dictpath = self._transstat(status, grouppath, dictpath, line)

        return mdata['L1_METADATA_FILE']

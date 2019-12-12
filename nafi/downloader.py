
import sys, os
from queue import Queue
from threading import Thread, Event

import sqlite3
from contextlib import contextmanager

from robobrowser import RoboBrowser as rb

from nafi.metadata import landsat8Manager

from nafi.landsat import landsatScene
from nafi.utils import LogEngine
from nafi.utils import Globals

from nafi.exceptions import downloadException

_NO_SET_ = -10000



class landsatDownloader:

    class LoginTimer(Thread):

        def __init__(self, timer, event, func):

            Thread.__init__(self, name='Credentials')

            self.duration = timer
            self.stopped = event
            self._handle_func = func

            self.logger = LogEngine().logger
            return

        def run(self):

            self.logger.debug("Credential renewal timer started.")

            while not self.stopped.wait(self.duration):
                self.logger.debug("Credential timer triggered.")
                # call the function
                self._handle_func()

            self.logger.debug("Credential renewal timer ended.")
            return

    def __init__(self, config=None):

        self.browser = None
        self.config_lk = config

        self.tasks = Queue()
        self.logger = LogEngine().logger

        self.timerEvent = Event()
        duration = self.config_lk['login_timer']
        self.timer = landsatDownloader.LoginTimer(duration, self.timerEvent, self.openConnection)

        self.initDatabase()

        return

    def getTasksQueue(self):

        return self.tasks

    def openConnection(self):

        browser = None

        if self.config_lk['online']:

            browser = rb(parser='html.parser', history=True)
            url_USGS_login = self.config_lk['url_login']

            browser.open(url_USGS_login)
            login = browser.get_form(action='/login/')
            login['username'] = self.config_lk['username']
            login['password'] = self.config_lk['password']
            browser.session.headers['Referer'] = url_USGS_login

            browser.submit_form(login)

            self.logger.debug('Credentials OK. Server response: %s', str(browser.response.status_code))

        return browser

    def initDatabase(self):

        try:
            self.dbase = downloadDataManager()
        except sqlite3.Error as error:
            self.logger.warning('Database: %s', error.args)
        return

    def startDownloads(self):

        dates = self.config_lk['dates']
        all_scenes = self.config_lk['scenes']
        # Maximum cloud cover over land (%)
        cc_land = self.config_lk['cc_land']

        self.browser = self.openConnection()

        try:

            # Start timer for credential renewal
            self.timer.start()

            metadb = landsat8Manager()

            # Iterate throught path/row scenes
            for path_scenes in all_scenes:

                for path in path_scenes:
                    for row in path_scenes[path]:

                        scene_metadata = metadb.getSceneProductIDs(path, row, dates[0], dates[-1], cc_land)

                        if self.browser is not None:

                            self.logger.info('Scenes queued for download:')
                            for meta in scene_metadata:
                                self.logger.info(repr(meta))

                            self.logger.info(' ')
                            for meta in scene_metadata:
                                self.downloadScene(meta)
                        else:
                            self.logger.info(' ')
                            for meta in scene_metadata:
                                self.offlineProcessing(meta)

            # Queue empty landsatScene as the end marker
            stopdownload = landsatScene()
            self.tasks.put(stopdownload)

            # Stop the credentials timer
            self.timerEvent.set()
            self.timerEvent.clear()
            self.timer.join()

            self.logger.info('Data downloader process exited.')

        except downloadException as error:

            self.logger.critical('Download Manager error encountered: %s', repr(error))
            self.logger.critical('Exiting Download Thread')

            # Stop the credentials timer
            self.timerEvent.set()
            self.timerEvent.clear()
            self.timer.join()

            # Queue empty landsatScene as the end marker
            stopdownload = landsatScene()
            self.tasks.put(stopdownload)

        return

    def downloadScene(self, mdata):
        """
        """

        working_dir = self.config_lk['working_d']

        # convert integers path, row to 3 characters string
        PATH = format(mdata.path, '03d')
        ROW = format(mdata.row, '03d')
        # remove dashes from date format
        ACQdate = mdata.acqdate.replace('-', '')

        outpath = os.path.join(working_dir, '{0}{1}'.format(PATH, ROW), ACQdate)
        outfile = os.path.join(outpath, mdata.product_id + '.tgz')

        # Compose download URL
        url = mdata.getSceneURL()
        if not url:
            raise downloadException('Download URL error. Returned empty string')

        self.logger.debug('Data URL: %s', url)

        response = self.browser.session.get(url, stream=True, headers={'Accept-Encoding': None})
        self.logger.debug('USGS Server response: %s', str(response.status_code))

        # if file exists on USGS server
        if response.status_code == 200:

            scene = landsatScene(mdata)
            scene.enableCleanup(self.config_lk['cleanup'])

            # Create directories only if there are data to download (avoid empty dirs)
            if os.path.exists(outpath) is False:
                os.makedirs(outpath)

            # Check if archive has already been downloaded.
            # Returns -1, if record doesn't exist
            f_size = _NO_SET_
            ar_size = self.dbase.getDownloadSize(os.path.basename(outfile), working_dir)

            if os.path.isfile(outfile) is True:
                f_size = os.path.getsize(outfile)
                # Set tarfile archive name to scene object
                scene.setTarArchive(os.path.basename(outfile))

            elif ar_size > 0:
                # record present in database, but scene tar file deleted?
                # Skip download and band projections in workflow
                f_size = ar_size

            if ar_size != f_size:

                # Delete record, archive might be missing
                self.dbase.deleteDownloadRecord(os.path.basename(outfile), working_dir)

                # Get file to download size
                total_length = 0
                content_length = response.headers.get('content-length')
                
                if content_length is None:
                    pass
                else:
                    total_length = int(response.headers.get('content-length'))

                with open(outfile, 'wb') as handle:   # the 'with' syntax if part of ContextManager it ensures the file is properly initialized and closed at the end

                    payload = 512
                    sys.stdout.write('\n')
                    mesg1 = '\t\t\tDownloading {0}:'.format(mdata.product_id + '.tgz')

                    if total_length == 0:
                        mesg2 = ' MB'
                    else:
                        f_size = int(total_length/Globals.MBYTES)
                        mesg2 = '/{0} MB'.format(f_size)

                    ichunk = 0
                    size_downloaded = 0
                    self.logger.info('Starting download scene [%s/%s] d=[%s]', PATH, ROW, ACQdate)

                    for chunk in response.iter_content(chunk_size=payload):
                        if chunk:   # filter out keep-alive new chunks
                            handle.write(chunk)

                            size_downloaded += len(chunk)

                            ichunk += 1
                            if (ichunk % 2000) == 0:
                                progress = int(ichunk * payload/(1024*1024))
                                sys.stdout.write('%s: %d%s   \r' % (mesg1, progress, mesg2))
                                sys.stdout.flush()

                    # Download has terminated
                    if os.path.isfile(outfile):
                        
                        if total_length == 0:  
                            total_length = size_downloaded

                        self.logger.debug('Size downloaded: [%d] -- Size on server [%d]', size_downloaded, total_length)

                        if size_downloaded == total_length:

                            self.logger.info('Scene [%s/%s] d=[%s], download complete: %d MB', PATH, ROW, ACQdate, int(os.path.getsize(outfile)/Globals.MBYTES))
                            self.dbase.logComplete(mdata, total_length, working_dir)

                            # Set tarfile archive name to scene object
                            scene.setTarArchive(os.path.basename(outfile))

                            # Queue landsatScene object for processing
                            self.logger.debug('Queuing scene [%s/%s], d=[%s]', PATH, ROW, ACQdate)
                            self.tasks.put(scene)

                        else:
                            self.logger.critical('%s download failed to complete.', os.path.basename(outfile))
                    else:
                        self.logger.critical('%s download failed.', os.path.basename(outfile))
            else:

                self.logger.info('Scene [%s/%s] d=[%s] has already been downloaded: %s MB', PATH, ROW, ACQdate, int(ar_size/Globals.MBYTES))

                # Queue landsatScene object for processing
                self.logger.debug('Queuing scene [%s/%s], d=[%s]', PATH, ROW, ACQdate)
                self.tasks.put(scene)
        else:
            self.logger.warning('Scene [%s/%s] for date [%s] is not avalaible.', PATH, ROW, ACQdate)

        return

    def offlineProcessing(self, mdata):

        working_dir = self.config_lk['working_d']

        # convert integers path, row to 3 characters string
        PATH = format(mdata.path, '03d')
        ROW = format(mdata.row, '03d')
        # remove dashes from date format
        ACQdate = mdata.acqdate.replace('-', '')


        # Check if archive has already been downloaded.
        # Returns -1, if record doesn't exist
        ar_size = self.dbase.getDownloadSize(mdata.product_id + '.tgz', working_dir)

        if ar_size != -1:

            scene = landsatScene(mdata)
            scene.enableCleanup(self.config_lk['cleanup'])

            # The archive has been downloaded previously
            self.logger.info('Scene [%s/%s] d=[%s] has already been downloaded: %s MB', PATH, ROW, ACQdate, int(ar_size/Globals.MBYTES))

            # Queue landsatScene object for processing
            self.logger.debug('Queuing scene [%s/%s], d=[%s]', PATH, ROW, ACQdate)
            self.tasks.put(scene)

        return


class downloadDataManager:
    """ Class responsable for creating the SQLite database and its tables
        and managing all records generated by landsatDownloader.
    """

    def __init__(self):

        self.wfname = self.__class__.__name__
        #self.wfname = 'TestDB'
        self.rootdir = self.getRootDirectory()
        self.createProcessTable()
        return

    def getRootDirectory(self):
        """ Return the directory where the download management database
            is created. By default it will be under '~\Documents\nafi\databases'
        """
        if Globals.DOWNLOADER_BASEDIR[0] == '~':
            return os.path.expanduser(Globals.DOWNLOADER_BASEDIR)
        else:
            return os.path.join('', Globals.DOWNLOADER_BASEDIR)

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
            raise downloadException('Downloader Database Error: {0}'.format(repr(error)))

        else:
            #print('commit transx')
            conn.commit()

        return conn

    def createProcessTable(self):
        """ Create the unique table used to log file download history
        """

        with self.getConnection() as conn:
            try:
                cur = conn.cursor()
                cur.execute("""\
                                CREATE TABLE IF NOT EXISTS downloads
                                (
                                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                                    Sensor VARCHAR(10),
                                    Coll_number INTEGER,
                                    Coll_category VARCHAR(2),
                                    Path INTEGER NOT NULL,
                                    Row INTEGER NOT NULL,
                                    acqdate DATE,
                                    Filename VARCHAR(100) NOT NULL,
                                    Filesize BIGINT NOT NULL,
                                    Location VARCHAR(300) NOT NULL,
                                    unique(Filename, Location)
                            );""")
                cur.close()

            except sqlite3.OperationalError:
                cur.close()

            except sqlite3.Error:
                cur.close()
                raise downloadException('Error creating table database \'downloads\'')
        return

    def logComplete(self, mdata, fsize, location):
        """ Create a database record in the 'downloads' table.
            The record contains sensor code, the landsat data collection
            mumber, the tar archive file name, the archive filesize and
            the download folder
        """

        fname = mdata.product_id + '.tgz'
        data = (mdata.sensor, mdata.coll_number, mdata.coll_type, mdata.path, mdata.row, mdata.acqdate, fname, fsize, location)

        with self.getConnection() as conn:
            try:
                cur = conn.cursor()
                cur.execute("""\
                            insert into downloads ('Sensor', 'Coll_number', 'Coll_category', 'Path', 'Row', 'acqdate', 'Filename', 'Filesize', 'Location')
                            values (?, ?, ?, ?, ?, ?, ?, ? ,?)""", data)
                cur.close()

            except sqlite3.Error as error:
                cur.close()
                raise downloadException('Error accessing database: {0}'.format(repr(error)))
        return

    def getDownloadSize(self, filenane, location):
        """ Return the downloaded file size for a given archive filename
            and download location
        """

        with self.getConnection() as conn:
            try:
                cur = conn.cursor()
                size = cur.execute("select Filesize from downloads where Filename=? and Location=?", (filenane, location)).fetchone()

                if size == None: size = (-1,)

            except sqlite3.Error as error:
                cur.close()
                raise downloadException('Error accessing database: {0}'.format(repr(error)))

        return size[0]

    def deleteDownloadRecord(self, file, location):
        """ delete a download record based on the identifying pair
            (archive filename, download location)
        """

        filename = os.path.basename(file)

        with self.getConnection() as conn:
            try:
                cur = conn.cursor()
                cur.execute("delete from downloads where Filename=? and Location=?", (filename, location))

            except sqlite3.Error as error:
                cur.close()
                raise downloadException('Error accessing database: {0}'.format(repr(error)))
        return

    def deleteAllRecords(self):
        """ Execute the SQL 'delete from downloads'
        """
        with self.getConnection() as conn:
            try:
                cur = conn.cursor()
                cur.execute("delete from downloads")

            except sqlite3.Error as error:
                cur.close()
                raise downloadException('Error accessing database: {0}'.format(repr(error)))
        return

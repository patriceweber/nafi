
import os
import tarfile
from tarfile import TarError

import re
from re import RegexFlag

from nafi.utils import LogEngine



class landsatScene:

    STOP = 'XXX'

    def __init__(self, metadata=None):

        if metadata:
            self.metadata = metadata

            # convert integers path, row to 3 characters string
            self.path = format(self.metadata.path, '03d')
            self.row = format(self.metadata.row, '03d')

            # remove dashes from date format
            self.acqdate = self.metadata.acqdate.replace('-', '')

            # set default directory
            self.directory = os.path.join('{0}{1}'.format(self.path, self.row), self.acqdate)
            self.tarfileloc = self.directory

            self.marker = ''

        else:
            self.path = self.row = self.acqdate = None
            self.directory = self.tarfileloc = None
            self.marker = landsatScene.STOP


        self.archive = None
        self.bCleanup = True
        self.logger = LogEngine().logger

        return

    def decodeProduct(self, filename):
        return self.metadata.decodeProduct(filename)

    def getNumberOfBands(self):
        return self.metadata.getNumberOfBands()

    def extractBands(self, target_directory):

        outpath = os.path.join(target_directory, self.directory)

        if self.archive is not None:
            f_archive = os.path.join(outpath, self.archive)

            if os.path.isfile(f_archive):
                self.logger.info('Extracting downloaded file: %s', os.path.basename(f_archive))

                try:
                    with tarfile.open(f_archive, 'r:gz') as tar:
                        def is_within_directory(directory, target):
                            
                            abs_directory = os.path.abspath(directory)
                            abs_target = os.path.abspath(target)
                        
                            prefix = os.path.commonprefix([abs_directory, abs_target])
                            
                            return prefix == abs_directory
                        
                        def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                        
                            for member in tar.getmembers():
                                member_path = os.path.join(path, member.name)
                                if not is_within_directory(path, member_path):
                                    raise Exception("Attempted Path Traversal in Tar File")
                        
                            tar.extractall(path, members, numeric_owner=numeric_owner) 
                            
                        
                        safe_extract(tar, os.path.join(outpath,"Bands"))

                except (IOError, TarError, EOFError) as error:
                    self.logger.critical('Error decompressing %s: %s', os.path.basename(f_archive), error.args)
                    outpath = None
            else:
                self.logger.critical('Data tar file: %s not found', os.path.basename(f_archive))
                outpath = None

            if outpath:
                self.logger.debug('Decompressing %s done', os.path.basename(f_archive))

        return None if outpath is None else os.path.join(outpath, 'Bands')


    def setTarArchive(self, archive=None):
        self.archive = archive

    def getTarArchive(self):
        return self.archive


    def endMarker(self):
        return self.marker

    def allowCleanup(self):
        return self.bCleanup

    def enableCleanup(self, flag=True):
        self.bCleanup = flag

    def disableCleanup(self):
        self.bCleanup = False

    def doCleanup(self, working_dir, exclusions):

        if self.allowCleanup():

            scene_dir = os.path.join(working_dir, self.directory)
            # Exclude file types, we want to keep from deletion
            extensions = ['sgrd', 'xml', 'mgrd', 'sdat', 'prj', 'pgw', 'tgz']

            for ext in exclusions:
                [extensions.remove(x) for x in extensions if x == ext]

            for root, dirs, files in os.walk(scene_dir):

                for ext in extensions:
                    pattern = '.{0}$'.format(ext)
                    [os.remove(os.path.join(root, x)) for x in files if re.search(pattern, x, flags=RegexFlag.IGNORECASE)]

                [os.remove(os.path.join(root, x)) for x in files if re.search(r'_B(\d+)\.TIF$', x, flags=RegexFlag.IGNORECASE)]


            self.logger.info('Clean up done.')

    def __repr__(self):

        return 'Scene [Sensor: {0}, PATH/ROW: [{1}/{2}], date: [MMDDYYYY]={3}'.format(self.metadata.sensor, self.path, self.row, self.acqdate)


import os, re
from re import RegexFlag

import logging

from tabulate import tabulate

from PIL import Image

from nafi.utils import Globals
from nafi.utils import natural_keys

from nafi.workflow import baseWF
from nafi.workflow import workflowException


# This workflow rely on the function 'executeSAGATool'
# run SAGA command on image files. The 'executeSAGATool'
# take three arguments:
#
#    tool_cmd: the SAGA command
#    output_file: the output file created by the SAGA command
#    task description: an optional string describing the processing step


class CY_Workflow(baseWF):
    """ CY_Workflow class implementation
    """

    def __init__(self, config, prepend=''):

        # Call base class constructor
        super(CY_Workflow, self).__init__(config)

        if not prepend:
            self.wf_name = self.__class__.__name__
        else:
            self.wf_name = prepend + self.__class__.__name__

        self.initDatabase()

        return

    def processScene(self, scene):
        """ Implementation of baseWF abstract method. This function is responsible for
            the initialization, the execution of the main workflow and clean up taks.
        """

        if scene is None:
            raise ValueError('Landsat scene not valid')

        self.scene = scene
        self.logger.info('Processing scene:  [%s/%s], acquired on [%s]', scene.path, scene.row, scene.acqdate)

        # If we force a rerun, delete all database entries for the current scene
        if self.force:
            self.deleteAllSteps()

        try:
            # If scene tar file exist, reproject bands?
            if self.scene.getTarArchive() is not None:
                self.reprojectBands()
            else:
                self.logger.info('Skipping band projections')

            # Execute main workflow
            self.runWorkFlow()

            # Do data cleanup
            if self.config['cleanup']:
                working_dir = self.config['working_d']
                exclusions = self.config['cleanup-exclude']
                self.scene.doCleanup(working_dir, exclusions)

        except workflowException as error:

            self.logger.critical('Workflow error encountered: %s', repr(error))
            self.scene.disableCleanup()
            self.logger.critical('Folder clean up disabled')
            raise ValueError('[{0}/{1}]'.format(self.scene.path, self.scene.row))

        # Log separation marker
        self.logger.info('-----------------')
        self.logger.info('  ')


    def reprojectBands(self):
        """ Reproject Landsat image coordinates to the WGS84 datum
        """
        PATH = self.scene.path
        ROW = self.scene.row
        DTDdate = self.scene.acqdate

        working_d = self.config['working_d']
        outpath_bands = os.path.join(working_d, self.scene.directory, 'Bands')

        # initialize p_uid for the function
        self.setInitialProcessUID(0)

        self.logger.info('Processing LC8 original bands')

        try:
            L8_bands = self.createExtractedBandList()

            for band in L8_bands:

                n_band = re.search(r'_B(\d+)\.TIF$', band, flags=RegexFlag.IGNORECASE).group(1)

                # Project to WGS
                f_source = os.path.join(outpath_bands, band)

                if re.search(r'(^[a-zA-Z0-9]+)_(.+)_B(\d+)\.TIF$', band, flags=RegexFlag.IGNORECASE):
                    gmatch = re.search(r'(^[a-zA-Z0-9]+)_(.+)_B(\d+)\.TIF$', band, flags=RegexFlag.IGNORECASE).groups()

                    if gmatch[0] == 'LC08':
                        sensor = 'LC8'
                    else:
                        sensor = gmatch[0]

                    fn_wgs = '{0}_{1}{2}_{3}_B{4}_{5}'.format(sensor, PATH, ROW, DTDdate, gmatch[2], 'WGS.sgrd')
                    f_target = os.path.join(outpath_bands, fn_wgs)
                else:
                    raise ValueError

                self.logger.info('Reproject Band %s: [%s] --> [%s]', n_band, band, fn_wgs)

                if self.config['saga_verbose'] is False:
                    #tool_cmd = ' -f=p{0} pj_proj4 4 -CRS_METHOD=1 -CRS_EPSG=4326 -SOURCE={1} -RESAMPLING=0 -TARGET_GRID={2}'.format('s', f_source, f_target)
                    tool_cmd = ' -f=p{0} pj_proj4 4 -CRS_METHOD=1 -CRS_EPSG=4326 -SOURCE={1} -RESAMPLING=0 -GRID={2}'.format('s', f_source, f_target)
                else:
                    #tool_cmd = ' -f=p pj_proj4 4 -CRS_METHOD=1 -CRS_EPSG=4326 -SOURCE={0} -RESAMPLING=0 -TARGET_GRID={1}'.format(f_source, f_target)
                    tool_cmd = ' -f=p pj_proj4 4 -CRS_METHOD=1 -CRS_EPSG=4326 -SOURCE={0} -RESAMPLING=0 -GRID={1}'.format(f_source, f_target)

                self.executeSAGATool(tool_cmd, f_target, 'Reproject Band {0} [sgrd]'.format(n_band))


                # Export reproject to tif
                f_tiff = os.path.splitext(f_target)[0] + '.tif'

                # tool_cmd = ' io_gdal 1 -GRIDS={0} -FILE={1} -FORMAT=7 -TYPE=0 -SET_NODATA=0 -NODATA=255.000000 -OPTIONS=COMPRESS=LZW'.format(f_target, f_tiff)
                tool_cmd = ' io_gdal 1 -GRIDS={0} -FILE={1} -FORMAT=7 -TYPE=0 -SET_NODATA=0 -NODATA=255.000000'.format(f_target, f_tiff)
                self.executeSAGATool(tool_cmd, f_tiff, 'Reproject Band {0} [tif]'.format(n_band))


        except (OSError, ValueError, IndexError) as error:

            self.logger.critical('Projection to WGS: %s completion error --> %s', band, error.args)
            self.logger.critical('Skipping scene: Path/Row= [%s/%s] date= [%s]', PATH, ROW, DTDdate)
            raise workflowException()


    def runWorkFlow(self):
        """ Main workflow execution function
        """

        PATH = self.scene.path
        ROW = self.scene.row
        DTDdate = self.scene.acqdate

        working_d = self.config['working_d']
        outpath_bands = os.path.join(working_d, self.scene.directory, 'Bands')

        # initialize p_uid for the current workflow. The initial p_uid should start
        # at 100 or above, not to interfere with other function like 'projectBandsWGS'
        self.setInitialProcessUID(1000)

#  STEP 1    Create a lookup table
#       ========================================

        # Lookup table of (band # --> 'Reprojected band filename'). We will need it!
        f_Bands = os.listdir(outpath_bands)
        L8_bands_WGS = [x for x in f_Bands if re.search(r'_B(\d+)\_WGS\.TIF$', x, flags=RegexFlag.IGNORECASE)]
        L8_bands_WGS.sort(key=natural_keys)

        if len(L8_bands_WGS) != self.scene.getNumberOfBands():
            raise workflowException('Missing WGS bands detected: {0} found instead of {1}'.format(len(L8_bands_WGS), '11'))

        self.logger.info('Building projected bands lookup table')

        Band_lookup = {}
        for fb in L8_bands_WGS:
            b_num = int(re.search(r'_B(\d+)\_WGS\.TIF$', fb, flags=RegexFlag.IGNORECASE).group(1))
            Band_lookup[b_num] = fb


#  STEP 2    Create a RGB composite file
#       ==========================================

        self.logger.info('Creating RGB composite image')

        RGBcomposite = os.path.join(outpath_bands, 'LC8{0}{1}{2}LGN00_RGBcomposite_WGS.sgrd'.format(PATH, ROW, DTDdate))

        #  RGB composite from bands [7, 6, 3]
        tool_cmd = ' grid_visualisation 3 -R_GRID={0} -R_METHOD=4 -R_STDDEV=2.000000'\
                    ' -G_GRID={1} -G_METHOD=4 -G_STDDEV=2.000000 -B_GRID={2} -B_METHOD=4 -B_STDDEV=2.000000 -A_GRID=NULL -RGB={3}'\
                    .format(os.path.join(outpath_bands, Band_lookup[7]), os.path.join(outpath_bands, Band_lookup[6]), os.path.join(outpath_bands, Band_lookup[3]), RGBcomposite)

        self.executeSAGATool(tool_cmd, RGBcomposite, 'Create RGB composite image')


#  STEP 3    Create kmz file from RGB composite file
#       ======================================================
        self.logger.info('Creating kmz from RGB composite image.')

        fout = os.path.join(outpath_bands, '{0}{1}_{2}_RGBcomposite.kmz'.format(PATH, ROW, DTDdate))

        tool_cmd = ' io_grid_image 2  -GRID={0} -SHADE=NULL -FILE={1} -OUTPUT=2 -COLOURING=5'.format(RGBcomposite, fout)

        self.executeSAGATool(tool_cmd, fout, 'Create kmz from RGB composite image')


#  STEP 4    Create and resize composite images (png)
#       ==========================================================

        self.logger.info('Creating PNG file Band(10,5,4)')

        # PNG from RGB composite bands [10, 5, 4]
        b_RED = os.path.join(outpath_bands, Band_lookup[10])
        b_GREEN = os.path.join(outpath_bands, Band_lookup[5])
        b_BLUE = os.path.join(outpath_bands, Band_lookup[4])

        fout = os.path.join(outpath_bands, '{0}{1}_{2}_{3}{4}{5}_rgb.sgrd'.format(PATH, ROW, DTDdate, '10', '5', '4'))

        tool_cmd = '  grid_visualisation 3 -R_GRID={0} -R_METHOD=3 -R_PERCTL_MIN=35.000000 -R_PERCTL_MAX=95.000000'\
                   ' -G_GRID={1} -G_METHOD=3 -G_PERCTL_MIN=35.000000 -G_PERCTL_MAX=95.000000'\
                   ' -B_GRID={2} -B_METHOD=3 -B_PERCTL_MIN=35.000000 -B_PERCTL_MAX=95.000000'\
                   ' -A_GRID=NULL -RGB={3}'.format(b_RED, b_GREEN, b_BLUE, fout)

        self.executeSAGATool(tool_cmd, fout, 'Create composite image Band(10,5,4)')

        f_png = os.path.splitext(fout)[0] + '.png'

        tool_cmd = ' io_grid_image 0 -GRID={0} -FILE={1} -FILE_KML=0 -COLOURING=4'.format(fout, f_png)
        self.executeSAGATool(tool_cmd, f_png, 'Create PNG image Band(10,5,4)')

        self.logger.info('Creating PNG file Band(7,6,3)')

        # Create thumbnail image Band(10,5,4)
        try:
            with Image.open(f_png) as img:
                img.thumbnail((512, 512), Image.ANTIALIAS)
                img.save(f_png)
        except Exception as error:
            raise workflowException(str(error.args))

        # PNG from RGB composite bands [7, 6, 3]
        b_RED = os.path.join(outpath_bands, Band_lookup[7])
        b_GREEN = os.path.join(outpath_bands, Band_lookup[6])
        b_BLUE = os.path.join(outpath_bands, Band_lookup[3])
        fout = os.path.join(outpath_bands, '{0}{1}_{2}_{3}{4}{5}_rgb.sgrd'.format(PATH, ROW, DTDdate, '7', '6', '3'))

        tool_cmd = '  grid_visualisation 3 -R_GRID={0}  -R_METHOD=3 -R_PERCTL_MIN=35.000000 -R_PERCTL_MAX=95.000000'\
                   ' -G_GRID={1} -G_METHOD=3 -G_PERCTL_MIN=35.000000 -G_PERCTL_MAX=95.000000'\
                   ' -B_GRID={2} -B_METHOD=3 -B_PERCTL_MIN=35.000000 -B_PERCTL_MAX=95.000000'\
                   ' -A_GRID=NULL -RGB={3}'.format(b_RED, b_GREEN, b_BLUE, fout)

        self.executeSAGATool(tool_cmd, fout, 'Create composite image Band(7,6,3)')

        f_png = os.path.splitext(fout)[0] + '.png'

        tool_cmd = ' io_grid_image 0 -GRID={0} -FILE={1} -FILE_KML=0 -COLOURING=4'.format(fout, f_png)
        self.executeSAGATool(tool_cmd, f_png, 'Create PNG image Band(7,6,3)')

        # Create thumbnail image Band(7,6,3)
        try:
            with Image.open(f_png) as img:
                img.thumbnail((512, 512), Image.ANTIALIAS)
                img.save(f_png)
        except Exception as error:
            raise workflowException(str(error.args))


#  STEP 5    Create Normalized Burn Ration (NBR)
#            and Mid Infrared Burn index (MIRB) files
#       ==========================================================

        self.logger.info('Calculating NBR')

        # NBR
        t_nbr = os.path.join(outpath_bands, 'LC8{0}{1}{2}LGN00_NBR.tif'.format(PATH, ROW, DTDdate))
        sg_nbr = os.path.splitext(t_nbr)[0] + '.sgrd'

        B7_WGS = os.path.join(outpath_bands, Band_lookup[7])
        B5_WGS = os.path.join(outpath_bands, Band_lookup[5])

        tool_cmd = ' grid_calculus 1 -GRIDS={0};{1} -RESULT={2} -FORMULA=(g1-g2)/(g1+g2) -NAME=Calculation -TYPE=7'.format(B7_WGS, B5_WGS, sg_nbr)
        self.executeSAGATool(tool_cmd, sg_nbr, 'Calculate NBR Image (sgrd)')


        #tool_cmd = ' io_gdal 1 -GRIDS={0} -FILE={1} -FORMAT=7 -TYPE=0 -SET_NODATA=1 -NODATA=2.000000 -OPTIONS=COMPRESS=LZW'.format(sg_nbr, t_nbr)
        tool_cmd = ' io_gdal 1 -GRIDS={0} -FILE={1} -FORMAT=7 -TYPE=0 -SET_NODATA=1 -NODATA=2.000000'.format(sg_nbr, t_nbr)
        self.executeSAGATool(tool_cmd, t_nbr, 'Calculate NBR Image (tif)')


        self.logger.info('Calculating MIBR')

        # MIRB
        t_mibr = os.path.join(outpath_bands, 'LC8{0}{1}{2}LGN00_MIBR.tif'.format(PATH, ROW, DTDdate))
        sg_mibr = os.path.splitext(t_mibr)[0] + '.sgrd'

        B7_WGS = os.path.join(outpath_bands, Band_lookup[7])
        B6_WGS = os.path.join(outpath_bands, Band_lookup[6])

        tool_cmd = ' grid_calculus 1 -GRIDS={0};{1} -RESULT={2} -FORMULA=(10*g1)-(9.8*g2)+2 -NAME=Calculation -TYPE=7'.format(B7_WGS, B6_WGS, sg_mibr)
        self.executeSAGATool(tool_cmd, sg_mibr, 'Calculate MIBR Image (sgrd)')


        #tool_cmd = ' io_gdal 1 -GRIDS={0} -FILE={1} -FORMAT=7 -TYPE=0 -SET_NODATA=1 -NODATA=2.000000 -OPTIONS=COMPRESS=LZW'.format(sg_mibr, t_mibr)
        tool_cmd = ' io_gdal 1 -GRIDS={0} -FILE={1} -FORMAT=7 -TYPE=0 -SET_NODATA=1 -NODATA=2.000000'.format(sg_mibr, t_mibr)
        self.executeSAGATool(tool_cmd, t_mibr, 'Calculate MIBR Image (tif)')


#  STEP 6    Create Automatic Segmentation of MIBR Image
#       ==========================================================
        #SEGMENTATION

        #self.logger.info('Starting automated segmentation')

        #f_out = os.path.join(outpath_bands, '{0}{1}{2}_MIBR_Automated_segments.shp'.format(PATH, ROW, DTDdate))

        #tool_cmd = ' imagery obia -FEATURES={0} -OBJECTS={1} -SEEDS_BAND_WIDTH=10.000000 -MAJORITY_RADIUS=1 -POSTPROCESSING=1'\
        #           ' -NCLUSTER=20 -SPLIT_CLUSTERS=0'.format(t_mibr, f_out)
        #self.executeSAGATool(tool_cmd, f_out, 'MIBR Image automated segmentation')


#  END WORKFLOW
        self.logger.info('  ')
        self.logger.info('Done processing scene: Path/Row= [%s/%s] date= [%s]', PATH, ROW, DTDdate)

        return


#==============================================================================
# Display the file naming convention used by the script as a table
# This helper function is for debugging purpose. The function is called when
# the script is run with '-d' option
#==============================================================================

    @staticmethod
    def fileNamingConvention():
        """ Display the file naming convention used by the 'CY_Workflow'
            as a table
        """
        path = '[PATH]'
        row = '[ROW]'
        date = '[YYYYMMDD]'
        doy = '[YYYYDOY]'
        s_band = '#'

        data_matrix = []

        print('\n\n')
        try:
            trow = []
            trow.append('Scene tar file (.tgz) ')
            trow.append('LC8{0}{1}{2}LGN00'.format(path, row, doy))
            data_matrix.append(trow)

            trow = []
            trow.append('L8 Band file (.tif)')
            trow.append('LC08_$$$$_{0}{1}_{2}_{2}_$$_B{3}'.format(path, row, date, s_band))
            data_matrix.append(trow)

            trow = []
            trow.append('Reprojected Band file (.sgrd|.tif)')
            trow.append('LC8_{0}{1}_{2}_B{3}_WGS'.format(path, row, date, s_band))
            data_matrix.append(trow)

            trow = []
            trow.append('RBG Composite file (.sgrd)')
            trow.append('LC8{0}{1}{2}LGN00_RGBcomposite_WGS'.format(path, row, date))
            data_matrix.append(trow)

            trow = []
            trow.append('RBG Composite KMZ file (.kmz)')
            trow.append('{0}{1}_{2}_RGBcomposite'.format(path, row, date))
            data_matrix.append(trow)

            trow = []
            trow.append('PNG Thumbnail files (.png)')
            trow.append('{0}{1}_{2}_{3}{4}{5}_rgb.png'.format(path, row, date, 'Br', 'Bg', 'Bb'))
            data_matrix.append(trow)

            trow = []
            trow.append('Normalized Burn Ratio NBR (.sgrd|.tif)')
            trow.append('LC8{0}{1}{2}LGN00_NBR.tif'.format(path, row, date))
            data_matrix.append(trow)

            trow = []
            trow.append('Mid Infrared Burn Index MIRB (.sgrd|.tif)')
            trow.append('LC8{0}{1}{2}LGN00_MIBR.tif'.format(path, row, date))
            data_matrix.append(trow)

            trow = []
            trow.append('MIRB Segmentation Image (.shp)')
            trow.append('{0}{1}{2}_MIBR_Automated_segments.shp'.format(path, row, date))
            data_matrix.append(trow)

            print(tabulate(data_matrix, headers=['File description', 'Naming Convention'], tablefmt='grid'))
            print(' ')

        except ValueError as error:
            logger = logging.getLogger(Globals.LOGNAME)
            logger.critical('Error creating the file naming convention table: %s', error.args)

        return


from time import sleep

from nafi.utils import LogEngine

from nafi.workflow import baseWF


class ExampleWorkflow(baseWF):


    def __init__(self, config, prepend=''):

        # Call base class constructor
        super(ExampleWorkflow, self).__init__(config)

        if not prepend:
            self.wf_name = self.__class__.__name__
        else:
            self.wf_name = prepend + self.__class__.__name__

        self.initDatabase()

        return

    @staticmethod
    def fileNamingConvention():

        logger = LogEngine().logger
        logger.info('From module -> nafi.Templates.ExampleWorkflow')
        logger.info('Calling \'fileNamingConvention\' function.')

    def processScene(self, scene):

        # This function should call at some point the
        # 'runWorkFlow' function

        # Set the scene to be processed
        self.scene = scene
        self.logger.info('\'processScene\' function call')

        # Run the workflow
        self.runWorkFlow()

        # Do something afterwards (cleanup etc...)

    def runWorkFlow(self):

        # Workflow example with 6 steps.
        # Each step is logged in the state database
        self.setInitialProcessUID(0)

# ===== Step 1
        if self.runSep(self.p_uid):  # Ckeck if step exists in database (True -> step needs to be run)
            sleep(1)
            self.logger.info('Executing Task %d for [%s/%s]', self.p_uid, self.scene.path, self.scene.row)
            # do something ......
            # if computation completed successfully, log current step (step_id) in database

            self.logWorkflowStep(self.p_uid, 'Step {0} description'.format(self.p_uid))
        else:
            # Step has previously been computed, do not run again unless '-force' is present in command line
            self.logger.info('Task %d for [%s/%s] has been found in the database', self.p_uid, self.scene.path, self.scene.row)

# ===== Step 2
        self.p_uid += 10
        if self.runSep(self.p_uid):
            sleep(1)
            self.logger.info('Executing Task %d for [%s/%s]', self.p_uid, self.scene.path, self.scene.row)
            # do something ......
            # if computation completed successfully, log current step (step_id) in database

            self.logWorkflowStep(self.p_uid, 'Step {0} description'.format(self.p_uid))
        else:
            self.logger.info('Task %d for [%s/%s] has been found in the database', self.p_uid, self.scene.path, self.scene.row)

# ===== Step 3
        self.p_uid += 10
        if self.runSep(self.p_uid):
            sleep(1)
            self.logger.info('Executing Task %d for [%s/%s]', self.p_uid, self.scene.path, self.scene.row)
            # do something ......
            # if computation completed successfully, log current step (step_id) in database

            self.logWorkflowStep(self.p_uid, 'Step {0} description'.format(self.p_uid))
        else:
            self.logger.info('Task %d for [%s/%s] has been found in the database', self.p_uid, self.scene.path, self.scene.row)

# ===== Step 4
        self.p_uid += 10
        if self.runSep(self.p_uid):
            sleep(1)
            self.logger.info('Executing Task %d for [%s/%s]', self.p_uid, self.scene.path, self.scene.row)
            # do something ......
            # if computation completed successfully, log current step (step_id) in database

            self.logWorkflowStep(self.p_uid, 'Step {0} description'.format(self.p_uid))
        else:
            self.logger.info('Task %d for [%s/%s] has been found in the database', self.p_uid, self.scene.path, self.scene.row)

# ===== Step 5
        self.p_uid += 10
        if self.runSep(self.p_uid):
            sleep(1)
            self.logger.info('Executing Task %d for [%s/%s]', self.p_uid, self.scene.path, self.scene.row)
            # do something ......
            # if computation completed successfully, log current step (step_id) in database

            self.logWorkflowStep(self.p_uid, 'Step {0} description'.format(self.p_uid))
        else:
            self.logger.info('Task %d for [%s/%s] has been found in the database', self.p_uid, self.scene.path, self.scene.row)

# ===== Step 6
        self.p_uid += 10
        if self.runSep(self.p_uid):
            sleep(1)
            self.logger.info('Executing Task %d for [%s/%s]', self.p_uid, self.scene.path, self.scene.row)
            # do something ......
            # if computation completed successfully, log current step (step_id) in database

            self.logWorkflowStep(self.p_uid, 'Step {0} description'.format(self.p_uid))
        else:
            self.logger.info('Task %d for [%s/%s] has been found in the database', self.p_uid, self.scene.path, self.scene.row)

        return


class ExampleWorkflowNoStates(baseWF):


    def __init__(self, config, prepend=''):

        # Call base class constructor
        super(ExampleWorkflowNoStates, self).__init__(config)

        if not prepend:
            self.wf_name = self.__class__.__name__
        else:
            self.wf_name = prepend + self.__class__.__name__

        self.initDatabase()

        return

    @staticmethod
    def fileNamingConvention():

        logger = LogEngine().logger
        logger.info('From module -> nafi.Templates.ExampleWorkflowNoStates')
        logger.info('Calling \'fileNamingConvention\' function.')

    def processScene(self, scene):

        # This function should call at some point the
        # 'runWorkFlow' function

        # Set the scene to be processed
        self.scene = scene
        self.logger('\'processScene\' function call')

        # Run the workflow
        self.runWorkFlow()

        # Do something afterwards (cleanup etc...)

    def runWorkFlow(self):

        # Workflow example with 4 steps.
        # Steps are not logged in the state database,
        # hence the whole computation is performed in case of rerun
        step_id = 0

# ===== Step 1
        step_id += 10
        self.logger.info('Executing Task %d for [%s/%s]', step_id, self.scene.path, self.scene.row)
        # do something ......
        # if computation completed successfully, log current step (step_id) in database


# ===== Step 2
        step_id += 10
        self.logger.info('Executing Task %d for [%s/%s]', step_id, self.scene.path, self.scene.row)
        # do something ......
        # if computation completed successfully, log current step (step_id) in database

# ===== Step 3
        step_id += 10
        self.logger.info('Executing Task %d for [%s/%s]', step_id, self.scene.path, self.scene.row)
        # do something ......
        # if computation completed successfully, log current step (step_id) in database


# ===== Step 4
        step_id += 10
        self.logger.info('Executing Task %d for [%s/%s]', step_id, self.scene.path, self.scene.row)
        # do something ......
        # if computation completed successfully, log current step (step_id) in database

        return

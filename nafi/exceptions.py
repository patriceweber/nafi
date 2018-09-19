

class metadataException(Exception):
    """ Downloader exception class. When this exception is raised,
        the downloader thread queue an 'end marker' scene in the FIFO shared
        queue and exit
    """

    def __init__(self, *args, **kwargs):
        super(metadataException, self).__init__(*args, **kwargs)
        return

    def __repr__(self, *args, **kwargs):
        return 'metadataException{0}'.format(self.args)


class MTLParseError(Exception):
    """ Custom exception: parse errors in Landsat or EO-1 MTL metadata files
    """

    def __init__(self, *args, **kwargs):
        super(MTLParseError, self).__init__(*args, **kwargs)
        return

    def __repr__(self, *args, **kwargs):
        return 'MTLParseError{0}'.format(self.args)


class downloadException(Exception):
    """ Downloader exception class. When this exception is raised,
        the downloader thread queue an 'end marker' scene in the FIFO shared
        queue and exit
    """

    def __init__(self, *args, **kwargs):
        super(downloadException, self).__init__(*args, **kwargs)
        return

    def __repr__(self, *args, **kwargs):
        return 'downloadException{0}'.format(self.args)


class workflowException(Exception):
    """ Workflow exception class. When such an exception is raised,
        the workflow execution is stopped
    """

    def __init__(self, *args, **kwargs):
        super(workflowException, self).__init__(*args, **kwargs)
        return

    def __repr__(self):

        return 'workflowException{0}'.format(self.args)

# Some header goes here
import logging
import os

def setup_logging(config):
    '''Set up logging'''
    if config.has_option('main', 'log_config'):
        log_config = config.get('main', 'log_config')
        f_path = os.path.expanduser(log_config)
        if not os.path.exists(f_path):
            raise Exception("Unable to read logging config file at %s" % f_path)
        logging.config.fileConfig(f_path)
    else:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(levelname)-8s %(message)s')


class ProjectConfig(object):
    def __init__(self, data):
        self.EXCEPT = set(data.pop('EXCEPT', None))
        self.ALL = data.pop('ALL', None)
        self.projects = {}
        for project, conf in data.iteritems():
            self.projects[project] = conf



# vim: ts=4 sw=4 sts=4 et


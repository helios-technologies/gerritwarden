# Some header goes here
from __future__ import absolute_import
import multiprocessing
import logging
import time
import json

import gerritwarden.jira_helper

class Warden(multiprocessing.Process):

    def __init__(self, gerrit_config,
                 jira_config,
                 project_config):
        multiprocessing.Process.__init__(self)
        self.log = logging.getLogger("gerritwarden")
        self.server = gerrit_config['server']
        self.port = int(gerrit_config['port'])
        self.username = gerrit_config['user']
        self.keyfile = gerrit_config['keyfile']
        self.connected = False
        self.jira_reviewfield = jira_config.pop('reviewfield')
        self.jira_config = jira_config
        self.jira_connected = False
        self.raw_project_config = project_config

    def connect(self):
        '''
        Connects to gerrit instance and start watching events
        '''
        import gerritlib.gerrit
        try:
            self.gerrit = gerritlib.gerrit.Gerrit(self.server, self.username,
                                                    self.port, self.keyfile)
            self.gerrit.startWatching()
            self.log.info('Start watching Gerrit event stream.')
            self.project_config = self._process_projects(self.raw_project_config)
            self.connected = True
        except:
            self.log.exception('Exception while connecting to gerrit')
            self.connected = False
            # Delay before attempting again.
            time.sleep(1)

    def connect_jira(self):
        '''
        Connects to jira and initializes jira wrapper
        '''
        import gerritwarden.jira_helper
        try:
            self.jira = gerritwarden.jira_helper.JiraWrapper(**self.jira_config)
            self.log.info('Connected to jira.')
            self.jira_connected = True
        except:
            self.log.exception('Unable to connect to jira.')
            self.jira_connected = False
            time.sleep(1)

    def get_projects(self):
        '''Return a list of projects'''
        return self.gerrit.listProjects()

    def _process_projects(self, project_config):
        '''Crate a uniform project config'''
        self.log.debug('Processing projects')
        raw_projects = self.get_projects()
        filtered_projects = ()
        updated_project_config = {}
        if project_config.ALL:
            filtered_projects = set(raw_projects)
        if project_config.projects:
            filtered_projects.update(set(project_config.projects.keys()))
        if project_config.EXCEPT:
            for excp in project_config.EXCEPT:
                filtered_projects.discard(excp)

        for project in filtered_projects:
            if project in project_config.projects:
                updated_project_config[project] = project_config.projects.get(project)
            else:
                updated_project_config[project] = project_config.ALL
        self.log.debug('Projects processed. passing back list')
        #self.log.debug(json.dumps(updated_project_config, indent=2, sort_keys=True))
        self.log.debug(updated_project_config)
        return updated_project_config

    def comment_added(self,data):
        pass

    def _process_state(self, event_type, data):
        self.log.debug("Processing %s event" % event_type )
        change_id = data['change']['id']
        commit_msg = self.gerrit.query(change_id, commit_msg=True)['commitMessage']
        issues = gerritwarden.jira_helper.get_jira_ids(commit_msg)
        reviewlink = data['change']['url']
        reviewfield = self.jira_reviewfield
        project = data['change']['project']
        transition = self.project_config[project]['events'][event_type]
        if issues:
            for issue in issues:
                self.log.debug("Adding link to %s" % issue )
                self.jira.add_review_link(issue, reviewfield, reviewlink)
                self.log.debug("Transitioning issues %s to %s" % (issue,
                                                                  transition) )
                comment = "Progressing issue due to %s event" % event_type
                self.jira.transition(issue, transition, comment)


    def _read(self, data):
        project_config = self.project_config
        try:
            project = data['change']['project']
            event = data['type']
            branch = data['change']['branch']
            cblob_set = set(project_config.get(project))
            transition = project_config[project]['events'][event]
            test_branch = project_config[project]['branches'][branch]
        except KeyError:
            # The data we care about was not present
            cblob_set = set()
            self.log.info('Potential actions for event: %s' % event)
        for prj in cblob_set:
            if data['type'] == 'comment-added':
                self.comment_added(data)
            elif data['type'] == 'patchset-created':
                self._process_state('patchset-created', data)
            elif data['type'] == 'change-merged':
                self._process_state('change-merged', data)

    def run(self):
        while True:
            while not self.connected:
                self.connect()
            while not self.jira_connected:
                self.connect_jira()
            try:
                event = self.gerrit.getEvent()
                self.log.info('Received event: %s' % event)
                self._read(event)
            except:
                self.log.exception('Exception encountered in event loop')
                if not self.gerrit.watcher_thread.is_alive():
                    # Start new gerrit connection. Don't need to restart
                    # bot, it will reconnect on its own.
                    self.connected = False
                if not self.jira.is_connected():
                    self.jira_connected = False

# vim: ts=4 sw=4 sts=4 et

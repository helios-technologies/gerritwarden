# Some header goes here
from __future__ import absolute_import
from urlparse import urlparse
from jira.client import JIRA
import logging
import re

def _is_id(value):
    '''Check if value is ID in the sense of integer'''
    try:
        int(value)
        return True
    except ValueError:
        return False

def get_jira_ids(data):
    '''Extract a list of all referenced jira_ids'''
    issue_re = re.compile(r"[A-Z]{1,3}-\d{1,8}")
    return issue_re.findall(data)

class JiraWrapper:
    '''Set of convenience methods around jira'''

    def __init__(self, url, login, password, sslcheck=False):
        self.url = url
        self.login = login
        self.options = {
                        'server': self.url,
                        'verify': sslcheck,
                       }
        authz = (login, password)
        self.jira = JIRA(options=self.options, basic_auth = authz)
        self.log = logging.getLogger('gerritwarden')

    def comment(self, issue, text):
        '''Add comment'''
        self.jira.add_comment(issue, text)

    def _get_tr_id_by_name(self, trans_available, name):
        '''Get transition id by target state name'''
        for trans in trans_available:
            if trans['to']['name'].lower() == name.lower():
                return trans['id']
        return None

    def transition(self, issue, state, comment, fields=None):
        '''Transition field with comment to specific state'''
        trans_available = self.jira.transitions(issue)
        trans_id = self._get_tr_id_by_name(trans_available, state)
        _issue = self.jira.issue(issue)
        if trans_id:
            self.jira.transition_issue(_issue, trans_id, comment=comment, fields=fields)
            return True
        else:
            return False

    def get_custom_fields(self, issue):
        c_fields = {}
        issue = self.jira.issue(issue)
        fields = issue.fields.__dict__
        for key, value in fields.items():
            if key.startswith('customfield'):
                c_fields[key] = value
        return c_fields

    def add_review_link(self, issue, reviewfield, reviewlink):
        '''Add a review link to issue. The link is added as an external link
        and as a value to Code Review field'''
        # Custom fields are starting with customfield_ prefix and a number
        # so we'll make sure that id will be enough
        try:
            int(reviewfield)
            reviewfield = "customfield_%s" % reviewfield
        except ValueError:
            str(reviewfield)
        c_fields = self.get_custom_fields(issue)
        s_issue = self.jira.issue(issue)
        try:
            rfield = c_fields[reviewfield]
        except KeyError:
            # There's no review field for this type of issue
            pass
        else:
            # TODO : make sure links are added once
            link_o = urlparse(reviewlink)
            changeid = link_o.path.split("/")[-1]
            app = link_o.hostname.split(".")[0]
            title = "%s - %s" % (app, changeid)
            link_object = {'url': reviewlink, 'title': title}
            gerrit_app = {'type': "gerrit", 'name': app}
            self.jira.add_remote_link(issue, object=link_object,
                                      globalId=reviewlink,
                                      application=gerrit_app)
            if c_fields.get(reviewfield):
                reviews = set(rfield.split("\n"))
                reviews.add(reviewlink)
                reviews_line = "\n".join(sorted(reviews))
                exec("s_issue.update(%s=reviews_line)" % reviewfield)
            else:
                exec("s_issue.update(%s=reviewlink)" % reviewfield)

    def is_connected(self):
        '''Check if connection to jira is still up'''
        if self.jira.server_info():
            return True
        else:
            return False


# vim: ts=4 sw=4 sts=4 et

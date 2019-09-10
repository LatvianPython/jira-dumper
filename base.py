from functools import partial
from typing import List
from dataclasses import dataclass, field

from jira import JIRA


def recurse_path(instance, path):
    current_attribute, *path = path
    try:
        if path:
            return recurse_path(getattr(instance, current_attribute), path)
        return getattr(instance, current_attribute)
    except (TypeError, AttributeError):
        return None


@dataclass
class JiraField:
    name: str = field(init=False)
    path: List[str]

    def __post_init__(self):
        try:
            _, self.name, *_ = self.path
        except ValueError:
            self.name, *_ = self.path


class Dumper:
    """Base class that implements dumping of common/basic Jira fields"""

    issue = JiraField(['key'])
    creation_date = JiraField(['fields', 'created'])
    status = JiraField(['fields', 'status', 'name'])
    issue_type = JiraField(['fields', 'issuetype', 'name'])
    summary = JiraField(['fields', 'summary'])
    resolution = JiraField(['fields', 'resolution', 'name'])
    assignee = JiraField(['fields', 'assignee', 'name'])
    reporter = JiraField(['fields', 'reporter', 'name'])
    priority = JiraField(['fields', 'priority', 'name'])
    original_estimate = JiraField(['fields', 'timetracking', 'originalEstimateSeconds'])
    remaining_estimate = JiraField(['fields', 'timetracking', 'remainingEstimateSeconds'])
    time_spent = JiraField(['fields', 'timetracking', 'timeSpentSeconds'])

    def __init__(self, server, jql, auth=None):
        self.jql = jql
        self.jira = JIRA(server=server, basic_auth=auth)

    def __enter__(self):
        self.jira_fields = {
            attribute: jira_field
            for attribute, jira_field in map(lambda attribute: (attribute, getattr(self, attribute, None)), dir(self))
            if isinstance(jira_field, JiraField)
        }

        fields = ','.join(tuple(jira_field.name for jira_field in self.jira_fields.values()))
        self.jira_issues = list(self.issue_generator(self.jql, fields, None))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def parse_issue(self, issue):
        return {name: recurse_path(issue, jira_field.path)
                for name, jira_field
                in self.jira_fields.items()
                }

    @property
    def issues(self):
        return (self.parse_issue(issue) for issue in self.jira_issues)

    def issue_generator(self, jql, fields, expand):
        page_size = 50
        search_issues = partial(self.jira.search_issues, maxResults=page_size,
                                jql_str=jql, fields=fields, expand=expand)
        start_at = 0
        issues = search_issues(startAt=start_at)
        while issues:
            for issue in issues:
                yield issue
            start_at += page_size
            issues = search_issues(startAt=start_at)

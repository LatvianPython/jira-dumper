from itertools import chain
from functools import partial
from typing import List

import jira


def recurse_path(instance, path):
    current_attribute, *path = path
    try:
        if path:
            return recurse_path(instance[current_attribute], path)
        return instance[current_attribute]
    except (TypeError, KeyError):
        return None


def get_fields(dumper):
    return {
        attribute: jira_field
        for attribute, jira_field
        in map(lambda attribute: (attribute, getattr(dumper, attribute, None)), dir(dumper))
        if isinstance(jira_field, IssueField)
    }


def extract_dict(structure, fields):
    return {name: recurse_path(structure, path)
            for name, path
            in fields.items()}


def extract_data(structure, fields, key_function):
    return dict(extract_dict(structure, fields),
                issue=key_function(structure))


def get_raw(x):
    return x.raw


def parse(parser, fields, data):
    parser = partial(parser, fields=fields)
    return map(parser, map(get_raw, data))


class IssueField(List):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.insert(0, 'fields')


class Dumper:
    """Base class that implements dumping of common/basic Jira fields"""

    creation_date = IssueField(['created'])
    status = IssueField(['status', 'name'])
    issue_type = IssueField(['issuetype', 'name'])
    summary = IssueField(['summary'])
    resolution = IssueField(['resolution', 'name'])
    assignee = IssueField(['assignee', 'name'])
    reporter = IssueField(['reporter', 'name'])
    priority = IssueField(['priority', 'name'])
    original_estimate = IssueField(['timetracking', 'originalEstimateSeconds'])
    remaining_estimate = IssueField(['timetracking', 'remainingEstimateSeconds'])
    time_spent = IssueField(['timetracking', 'timeSpentSeconds'])

    worklog_fields = {
        'author': ['author', 'name'],
        'comment': ['comment'],
        'started': ['started'],
        'time_spent': ['timeSpentSeconds']
    }

    get_transitions = True

    def __init__(self, server, jql, auth=None):
        self.jql = jql
        self.jira = jira.JIRA(server=server, basic_auth=auth)

    def __enter__(self):
        self.jira_fields = get_fields(self)

        expand = 'changelog' if self.get_transitions else None

        fields = ','.join(tuple(map(lambda x: x[1], self.jira_fields.values())))
        self.jira_issues = list(self.issue_generator(self.jql, fields, expand))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @property
    def transitions(self):
        history_fields = {
            'author': ['author', 'name'],
            'created': ['created']
        }

        item_fields = {
            'from': ['fromString'],
            'to': ['toString']
        }

        def get_items(histories):
            issue, histories = histories
            yield from (
                dict(**extract_dict(history, history_fields),
                     **extract_dict(item, item_fields),
                     issue=issue)
                for history in histories
                for item in history['items']
                if item['field'] == 'Status'
            )

        def get_histories(issue):
            return (issue.key, recurse_path(get_raw(issue), ['changelog', 'histories']))

        return map(get_items, map(get_histories, self.jira_issues))

    @property
    def issues(self):
        parser = partial(extract_data, key_function=lambda x: x['key'])
        return parse(parser, self.jira_fields, self.jira_issues)

    @property
    def worklogs(self):
        return chain.from_iterable(map(self.issue_worklogs, map(lambda issue: issue.key, self.jira_issues)))

    def issue_worklogs(self, issue):
        parser = partial(extract_data, key_function=lambda x: issue)
        return parse(parser, self.worklog_fields, self.jira.worklogs(issue=issue))

    def issue_generator(self, jql, fields, expand):
        page_size = 50
        search_issues = partial(self.jira.search_issues, maxResults=page_size,
                                jql_str=jql, fields=fields, expand=expand)
        start_at = 0
        issues = search_issues(startAt=start_at)
        while issues:
            yield from issues
            start_at += page_size
            issues = search_issues(startAt=start_at)

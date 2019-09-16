from functools import partial
from itertools import chain
from typing import List
import inspect

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


def parse_list(issues, path_to_list, fields):
    get_list = partial(recurse_path, path=path_to_list)
    return (
        dict(**extract_dict(list_item, fields),
             issue=issue['key'])
        for issue in map(get_raw, issues)
        for list_item in get_list(issue) or []
    )


class IssueField(List):
    pass


class Dumper:
    """Base class that implements dumping of common/basic Jira fields"""

    creation_date = IssueField(['fields', 'created'])
    status = IssueField(['fields', 'status', 'name'])
    issue_type = IssueField(['fields', 'issuetype', 'name'])
    summary = IssueField(['fields', 'summary'])
    resolution = IssueField(['fields', 'resolution', 'name'])
    assignee = IssueField(['fields', 'assignee', 'name'])
    reporter = IssueField(['fields', 'reporter', 'name'])
    priority = IssueField(['fields', 'priority', 'name'])
    original_estimate = IssueField(['fields', 'timetracking', 'originalEstimateSeconds'])
    remaining_estimate = IssueField(['fields', 'timetracking', 'remainingEstimateSeconds'])
    time_spent = IssueField(['fields', 'timetracking', 'timeSpentSeconds'])

    worklog_fields = {
        'author': ['author', 'name'],
        'comment': ['comment'],
        'started': ['started'],
        'time_spent': ['timeSpentSeconds']
    }

    history_fields = {
        'author': ['author', 'name'],
        'created': ['created']
    }

    item_fields = {
        'from': ['fromString'],
        'to': ['toString']
    }

    comment_fields = {
        'created': ['created'],
        'author': ['author', 'name'],
        'body': ['body']
    }

    fix_version_fields = {
        'name': ['name'],
        'description': ['description'],
        'release_date': ['releaseDate']
    }

    sla_overview_fields = {
        'status': ['status'],
        'name': ['slaName'],
        'working_duration_seconds': ['workingDurationAsSeconds'],
        'sla_value_minutes': ['slaValueAsMinutes']
    }

    get_transitions = True
    get_comments = True
    get_fix_versions = True

    def __init__(self, server, jql, auth=None, tqdm=False):
        self.jql = jql
        self.jira = jira.JIRA(server=server, basic_auth=auth)

        if tqdm:
            import tqdm
            self.tqdm = tqdm
        else:
            self.tqdm = None

    def __enter__(self):
        self.jira_fields = get_fields(self)

        expand = ['changelog'] if self.get_transitions else []

        expand = [field[0]
                  for field
                  in self.jira_fields.values()
                  if field[0] != 'fields'] + expand

        fields = [field[1]
                  for field
                  in self.jira_fields.values()]

        if self.get_comments:
            fields.append('comment')
        if self.get_fix_versions:
            fields.append('fixVersions')

        fields = ','.join(tuple(fields))
        expand = ','.join(tuple(expand))

        if self.tqdm is not None:
            self.jira_issues = list(self.tqdm.tqdm(self.issue_generator(self.jql, fields, expand), desc='Issues'))
        else:
            self.jira_issues = list(self.issue_generator(self.jql, fields, expand))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @property
    def fix_versions(self):
        fix_version_path = ['fields', 'fixVersions']
        return parse_list(self.jira_issues, fix_version_path, self.fix_version_fields)

    @property
    def comments(self):
        comment_path = ['fields', 'comment', 'comments']
        return parse_list(self.jira_issues, comment_path, self.comment_fields)

    @property
    def transitions(self):
        def get_items(histories):
            issue, histories = histories
            return (
                dict(**extract_dict(history, self.history_fields),
                     **extract_dict(item, self.item_fields),
                     issue=issue)
                for history in histories
                for item in history['items']
                if item['field'] == 'status'
            )

        def get_histories(issue):
            return issue.key, recurse_path(get_raw(issue), ['changelog', 'histories'])

        return chain.from_iterable(map(get_items, map(get_histories, self.jira_issues)))

    @property
    def issues(self):
        parser = partial(extract_data, key_function=lambda x: x['key'])
        return parse(parser, self.jira_fields, self.jira_issues)

    @property
    def worklogs(self):
        return chain.from_iterable(map(self.issue_worklogs, map(lambda issue: issue.key, self.jira_issues)))

    @property
    def sla_overview(self):
        return chain.from_iterable(map(self.get_sla, map(lambda x: x.key, self.jira_issues)))

    def __getattribute__(self, item):
        if super().__getattribute__('tqdm') is not None:
            properties = [(name, object_)
                          for name, object_
                          in inspect.getmembers(Dumper)
                          if '__' not in name and inspect.isdatadescriptor(object_)]

            if item in [name for name, _ in properties]:
                return self.tqdm.tqdm(super().__getattribute__(item), desc=item)

        return super().__getattribute__(item)



    def issue_worklogs(self, issue):
        parser = partial(extract_data, key_function=lambda x: issue)
        return parse(parser, self.worklog_fields, self.jira.worklogs(issue=issue))

    def get_sla(self, issue):
        # noinspection PyProtectedMember
        # https://confluence.snapbytes.com/display/TTS/REST+Services
        return (
            dict(extract_dict(sla, self.sla_overview_fields), issue=issue)
            for sla
            in self.jira._get_json(path=issue, params=None, base='{server}/rest/tts-api/latest/sla/overview/{path}')
        )

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

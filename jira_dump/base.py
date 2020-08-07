from collections import UserList
from functools import partial
from itertools import chain

import jira


def get_fields(dumper):
    return {
        attribute: jira_field
        for attribute, jira_field in map(
            lambda attribute: (attribute, getattr(dumper, attribute, None)), dir(dumper)
        )
        if isinstance(jira_field, IssueField)
    }


def dict_value(dictionary, path):
    for key in path:
        try:
            dictionary = dictionary[key]
        except (KeyError, TypeError):
            return None
    return dictionary


def extract_dict(dictionary, fields):
    return {name: dict_value(dictionary, path) for name, path in fields.items()}


def nested_parser(path_to_list, fields):
    def parse_issue(issue):
        return (
            dict(**extract_dict(list_item, fields), issue=issue["key"])
            for list_item in dict_value(issue, path=path_to_list) or []
        )

    return parse_issue


def histories_parser(field, history_fields, item_fields):
    def get_items(issue, histories):
        return (
            dict(
                **extract_dict(history, history_fields),
                **extract_dict(item, item_fields),
                issue=issue
            )
            for history in histories
            for item in history["items"]
            if item["field"] == field
        )

    def get_histories(issue):
        return issue["key"], dict_value(issue, ["changelog", "histories"])

    def get_histories_fields(issue):
        return get_items(*get_histories(issue))

    return get_histories_fields


class IssueField(UserList):
    pass


class Dumper:
    """Base class that implements dumping of common/basic Jira fields"""

    issue = IssueField(["key"])
    creation_date = IssueField(["fields", "created"])
    status = IssueField(["fields", "status", "name"])
    issue_type = IssueField(["fields", "issuetype", "name"])
    summary = IssueField(["fields", "summary"])
    resolution = IssueField(["fields", "resolution", "name"])
    assignee = IssueField(["fields", "assignee", "name"])
    reporter = IssueField(["fields", "reporter", "name"])
    priority = IssueField(["fields", "priority", "name"])
    original_estimate = IssueField(
        ["fields", "timetracking", "originalEstimateSeconds"]
    )
    remaining_estimate = IssueField(
        ["fields", "timetracking", "remainingEstimateSeconds"]
    )
    time_spent = IssueField(["fields", "timetracking", "timeSpentSeconds"])

    worklog_fields = {
        "author": ["author", "name"],
        "comment": ["comment"],
        "started": ["started"],
        "time_spent": ["timeSpentSeconds"],
    }

    history_fields = {"author": ["author", "name"], "created": ["created"]}

    item_fields = {"from": ["fromString"], "to": ["toString"]}

    comment_fields = {
        "created": ["created"],
        "author": ["author", "name"],
        "body": ["body"],
    }

    fix_version_fields = {
        "name": ["name"],
        "description": ["description"],
        "release_date": ["releaseDate"],
    }

    sla_overview_fields = {
        "status": ["status"],
        "name": ["slaName"],
        "working_duration_seconds": ["workingDurationAsSeconds"],
        "sla_value_minutes": ["slaValueAsMinutes"],
    }

    get_transitions = True
    get_comments = True
    get_fix_versions = True

    def __init__(self, server, jql, auth=None):
        self.jql = jql
        self.jira = jira.JIRA(server=server, basic_auth=auth)

    def __enter__(self):
        self.jira_fields = get_fields(self)

        expand = ["changelog"] if self.get_transitions else []

        expand = [
            field[0] for field in self.jira_fields.values() if field[0] != "fields"
        ] + expand

        fields = [field[1] for field in self.jira_fields.values() if len(field) > 1]

        if self.get_comments:
            fields.append("comment")
        if self.get_fix_versions:
            fields.append("fixVersions")

        fields, expand = ",".join(tuple(fields)), ",".join(tuple(expand))

        self.jira_issues = [
            issue.raw for issue in self.issue_generator(self.jql, fields, expand)
        ]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def history_items(self, field_type):
        return chain.from_iterable(
            map(
                histories_parser(field_type, self.history_fields, self.item_fields),
                self.jira_issues,
            )
        )

    @property
    def fix_versions(self):
        fix_version_path = ["fields", "fixVersions"]
        return chain.from_iterable(
            map(
                nested_parser(fix_version_path, self.fix_version_fields),
                self.jira_issues,
            )
        )

    @property
    def comments(self):
        comment_path = ["fields", "comment", "comments"]
        return chain.from_iterable(
            map(nested_parser(comment_path, self.comment_fields), self.jira_issues)
        )

    @property
    def transitions(self):
        return self.history_items("status")

    @property
    def issues(self):
        return map(partial(extract_dict, fields=self.jira_fields), self.jira_issues)

    @property
    def worklogs(self):
        return chain.from_iterable(map(self.issue_worklogs, self.jira_issues))

    @property
    def sla_overview(self):
        return chain.from_iterable(map(self.get_sla, self.jira_issues))

    def issue_worklogs(self, issue):
        return (
            dict(extract_dict(item.raw, self.worklog_fields), issue=issue["key"])
            for item in self.jira.worklogs(issue=issue["key"])
        )

    def get_sla(self, issue):
        # noinspection PyProtectedMember
        # https://confluence.snapbytes.com/display/TTS/REST+Services
        return (
            dict(extract_dict(sla, self.sla_overview_fields), issue=issue["key"])
            for sla in self.jira._get_json(
                path=issue["key"],
                params=None,
                base="{server}/rest/tts-api/latest/sla/overview/{path}",
            )
        )

    def issue_generator(self, jql, fields, expand):
        page_size = 50
        search_issues = partial(
            self.jira.search_issues,
            maxResults=page_size,
            jql_str=jql,
            fields=fields,
            expand=expand,
        )
        start_at = 0
        issues = search_issues(startAt=start_at)
        while issues:
            yield from issues
            start_at += page_size
            issues = search_issues(startAt=start_at)

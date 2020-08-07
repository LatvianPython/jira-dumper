from __future__ import annotations

from functools import partial
from itertools import chain
from types import TracebackType
from typing import (
    Dict,
    List,
    Any,
    Union,
    Iterator,
    Callable,
    Mapping,
    Tuple,
    Optional,
    Type,
    TYPE_CHECKING,
)

import jira


def get_fields(dumper: Dumper) -> FieldMap:
    return {
        attribute: jira_field
        for attribute, jira_field in map(
            lambda attribute: (attribute, getattr(dumper, attribute, None)), dir(dumper)
        )
        if isinstance(jira_field, IssueField)
    }


def dict_value(dictionary: Dict[str, Any], path: FieldPath) -> Any:
    for key in path:
        try:
            dictionary = dictionary[key]
        except (KeyError, TypeError):
            return None
    return dictionary


def extract_dict(dictionary: Dict[str, Any], fields: FieldMap) -> Dict[str, Any]:
    return {name: dict_value(dictionary, path) for name, path in fields.items()}


def nested_parser(
    path_to_list: FieldPath, fields: FieldMap
) -> Callable[[Dict[str, Any]], Iterator[Dict[str, Any]]]:
    def parse_issue(issue: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        return (
            dict(**extract_dict(list_item, fields), issue=issue["key"])
            for list_item in dict_value(issue, path=path_to_list) or []
        )

    return parse_issue


def histories_parser(
    field: str, history_fields: FieldMap, item_fields: FieldMap
) -> Callable[[Dict[str, Any]], Iterator[Dict[str, Any]]]:
    def get_items(
        issue: str, histories: List[Dict[str, Any]]
    ) -> Iterator[Dict[str, str]]:
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

    def get_histories(issue: Dict[str, Any]) -> Tuple[str, Any]:
        return issue["key"], dict_value(issue, IssueField(["changelog", "histories"]))

    def get_histories_fields(issue: Dict[str, Any]) -> Iterator[Dict[str, str]]:
        return get_items(*get_histories(issue))

    return get_histories_fields


class IssueField(List[str]):
    pass


if TYPE_CHECKING:
    FieldPath = Union[IssueField, List[str]]
    FieldMap = Mapping[str, FieldPath]


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

    def __init__(
        self, server: str, jql: Optional[str] = None, auth: Optional[str] = None
    ) -> None:
        self.jql = jql or ""
        self.jira = jira.JIRA(server=server, basic_auth=auth)

    def __enter__(self) -> Dumper:
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

        self.jira_issues = [
            issue.raw
            for issue in self.issue_generator(
                self.jql, ",".join(tuple(fields)), ",".join(tuple(expand))
            )
        ]
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        pass

    def history_items(self, field_type: str) -> Iterator[Dict[str, str]]:
        return chain.from_iterable(
            map(
                histories_parser(field_type, self.history_fields, self.item_fields),
                self.jira_issues,
            )
        )

    @property
    def fix_versions(self) -> Iterator[Dict[str, str]]:
        fix_version_path = ["fields", "fixVersions"]
        return chain.from_iterable(
            map(
                nested_parser(fix_version_path, self.fix_version_fields),
                self.jira_issues,
            )
        )

    @property
    def comments(self) -> Iterator[Dict[str, str]]:
        comment_path = ["fields", "comment", "comments"]
        return chain.from_iterable(
            map(nested_parser(comment_path, self.comment_fields), self.jira_issues)
        )

    @property
    def transitions(self) -> Iterator[Dict[str, str]]:
        return self.history_items("status")

    @property
    def issues(self) -> Iterator[Dict[str, str]]:
        return map(partial(extract_dict, fields=self.jira_fields), self.jira_issues)

    @property
    def worklogs(self) -> Iterator[Dict[str, str]]:
        return chain.from_iterable(map(self.issue_worklogs, self.jira_issues))

    @property
    def sla_overview(self) -> Iterator[Dict[str, str]]:
        return chain.from_iterable(map(self.get_sla, self.jira_issues))

    def issue_worklogs(self, issue: Dict[str, Any]) -> Iterator[Dict[str, str]]:
        return (
            dict(extract_dict(item.raw, self.worklog_fields), issue=issue["key"])
            for item in self.jira.worklogs(issue=issue["key"])
        )

    def get_sla(self, issue: Dict[str, str]) -> Iterator[Dict[str, str]]:
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

    def issue_generator(  # type: ignore
        self, jql: str, fields: str, expand: str
    ) -> Iterator[jira.Issue]:
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

import inspect

import pandas as pd

from jira_dump import Dumper, IssueField
from jira_dump.base import dict_value, get_fields, extract_dict


def test_dumper_basic(dumper):
    issues = list(dumper.issues)
    assert len(issues) == 1

    issue = issues[0]
    assert issue["status"] == "Running automatic tests"
    assert issue["issue"] == "TEST-42"


def test_subclassing(patch_jira):
    class CustomDumper(Dumper):
        test = IssueField(["fields", "test"])

    with CustomDumper(server="https://jira.server.com") as dumper:
        for issue in dumper.issues:
            assert "test" in issue


def test_issue_field():
    field = IssueField(["fields", "2", "3"])

    assert field[1] == "2"
    assert len(field) == 3
    assert field[0] == "fields"


def test_dict_value():
    assert dict_value({"1": {"2": {"3": "end"}}}, ["1", "2", "3"]) == "end"
    assert dict_value({"1": "end"}, ["a", "b", "c"]) is None


def test_get_fields(patch_jira):
    class CustomDumper(Dumper):
        test = IssueField(["test1", "test2"])

    fields = get_fields(CustomDumper("", ""))
    assert "test" in fields
    assert len(fields.keys()) > len(get_fields(Dumper("", "")))


def test_extract_dict():
    parsed_issue = extract_dict(
        {"fields": {"a": "b"}, "key": "TEST-123"}, {"c": IssueField(["fields", "a"])},
    )

    assert "c" in parsed_issue
    assert parsed_issue["c"] == "b"


def test_worklogs(dumper):
    worklogs = list(dumper.worklogs)

    assert len(worklogs) == 10
    assert worklogs[0]["author"] == "john.doe"
    assert sorted(worklogs[0].keys()) == [
        "author",
        "comment",
        "issue",
        "started",
        "time_spent",
    ]


def test_transitions(dumper):
    transitions = list(dumper.transitions)

    assert len(transitions) == 3

    transition = transitions[0]
    assert transition["author"] == "john@server.com"
    assert list(transition.keys()) == ["author", "created", "from", "to", "issue"]


def test_comments(dumper):
    comments = list(dumper.comments)

    assert len(comments) == 1

    comment = comments[0]
    assert comment["author"] == "jane.doe@server.com"
    assert sorted(list(comment.keys())) == sorted(
        ["author", "created", "body", "issue"]
    )


def test_fix_versions(dumper):
    fix_versions = list(dumper.fix_versions)

    assert len(fix_versions) == 1

    fix_version = fix_versions[0]
    assert fix_version["name"] == "RELEASE_05"
    assert sorted(list(fix_version.keys())) == sorted(
        ["description", "name", "release_date", "issue"]
    )


def test_sla_overview(dumper):
    sla_overview = list(dumper.sla_overview)

    assert len(sla_overview) == 2

    sla = sla_overview[0]
    assert sla["status"] == "SUCCESS"


def test_dataframes(dumper):
    for name, object_ in inspect.getmembers(Dumper):
        if "__" not in name and inspect.isdatadescriptor(object_):
            df = pd.DataFrame(getattr(dumper, name))
            assert "issue" in df.columns
            assert len(df) > 0

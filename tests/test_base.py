import inspect

import pandas as pd
import tqdm

from jira_dump import Dumper, IssueField
from jira_dump.base import recurse_path, get_fields, extract_data


def test_dumper_basic(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        issues = list(dumper.issues)
        assert len(issues) == 1

        issue = issues[0]
        assert issue['status'] == 'Running automatic tests'
        assert issue['issue'] == 'TEST-42'


def test_subclassing(patch_jira):
    class CustomDumper(Dumper):
        test = IssueField(['fields', 'test'])

    with CustomDumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        for issue in dumper.issues:
            assert 'test' in issue


def test_issue_field():
    field = IssueField(['fields', '2', '3'])

    assert field[1] == '2'
    assert len(field) == 3
    assert field[0] == 'fields'


def test_recurse_path():
    assert recurse_path({'1': {'2': {'3': 'end'}}}, ['1', '2', '3']) == 'end'
    assert recurse_path({'1': 'end'}, ['a', 'b', 'c']) is None


def test_get_fields():
    class CustomDumper(Dumper):
        test = IssueField(['test1', 'test2'])

    fields = get_fields(CustomDumper)
    assert 'test' in fields
    assert len(fields.keys()) > len(get_fields(Dumper))


def test_extract_data():
    parsed_issue = extract_data({'fields': {'a': 'b'}, 'key': 'TEST-123'},
                                {'c': IssueField(['fields', 'a'])},
                                lambda x: x['key']
                                )

    assert 'c' in parsed_issue
    assert parsed_issue['c'] == 'b'
    assert parsed_issue['issue'] == 'TEST-123'


def test_worklogs(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        worklogs = list(dumper.worklogs)

        assert len(worklogs) == 10
        assert worklogs[0]['author'] == 'john.doe'


def test_transitions(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        transitions = list(dumper.transitions)

        assert len(transitions) == 3

        transition = transitions[0]
        assert transition['author'] == 'john@server.com'
        assert list(transition.keys()) == ['author', 'created', 'from', 'to', 'issue']


def test_comments(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        comments = list(dumper.comments)

        assert len(comments) == 1

        comment = comments[0]
        assert comment['author'] == 'jane.doe@server.com'
        assert sorted(list(comment.keys())) == sorted(['author', 'created', 'body', 'issue'])


def test_fix_versions(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        fix_versions = list(dumper.fix_versions)

        assert len(fix_versions) == 1

        fix_version = fix_versions[0]
        assert fix_version['name'] == 'RELEASE_05'
        assert sorted(list(fix_version.keys())) == sorted(['description', 'name', 'release_date', 'issue'])


def test_sla_overview(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        sla_overview = list(dumper.sla_overview)

        assert len(sla_overview) == 2

        sla = sla_overview[0]
        assert sla['status'] == 'SUCCESS'


def test_dataframes(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        for name, object_ in inspect.getmembers(Dumper):
            if '__' not in name and inspect.isdatadescriptor(object_):
                df = pd.DataFrame(getattr(dumper, name))
                assert len(df) > 0


def test_tqdm(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None, tqdm=True) as dumper:
        assert isinstance(dumper.issues, tqdm.tqdm)

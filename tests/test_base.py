from base import Dumper, IssueField, recurse_path, get_fields, extract_data


def test_dumper_basic(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        issues = list(dumper.issues)
        assert len(issues) == 1

        issue = issues[0]
        assert issue['status'] == 'Running automatic tests'
        assert issue['issue'] == 'TEST-42'


def test_subclassing(patch_jira):
    class CustomDumper(Dumper):
        test = IssueField(['test'])

    with CustomDumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        for issue in dumper.issues:
            assert 'test' in issue


def test_jira_field():
    field = IssueField(['2', '3'])

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


def test_parse_issue():
    parsed_issue = extract_data({'fields': {'a': 'b'}, 'key': None},
                                {'c': IssueField(['a'])},
                                lambda x: x['key']
                                )

    assert 'c' in parsed_issue
    assert parsed_issue['c'] == 'b'


def test_worklogs(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        worklogs = list(dumper.worklogs)

        assert len(worklogs) == 10
        assert worklogs[0]['author'] == 'john.doe'

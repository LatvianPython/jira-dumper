from base import Dumper, JiraField, recurse_path, get_fields


def test_dumper_basic(patch_jira):
    with Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        issues = list(dumper.issues)
        assert len(issues) == 1

        issue = issues[0]
        assert issue['status'] == 'Running automatic tests'
        assert issue['issue'] == 'TEST-42'


def test_subclassing(patch_jira):
    class CustomDumper(Dumper):
        test = JiraField(['test'])

    with CustomDumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        for issue in dumper.issues:
            assert 'test' in issue


def test_jira_field():
    field = JiraField(['2', '3'])

    assert field.name == '2'
    assert len(field.path) == 3
    assert field.path[0] == 'fields'


def test_recurse_path():
    assert recurse_path({'1': {'2': {'3': 'end'}}}, ['1', '2', '3']) == 'end'
    assert recurse_path({'1': 'end'}, ['a', 'b', 'c']) is None


def test_get_fields():
    class CustomDumper(Dumper):
        test = JiraField(['test1', 'test2'])

    fields = get_fields(CustomDumper)
    assert 'test' in fields
    assert len(fields.keys()) > len(get_fields(Dumper))


def test_parse_issue():
    parsed_issue = Dumper.parse_issue({'fields': {'a': 'b'}, 'key': None}, {'c': JiraField(['a'])})

    assert 'c' in parsed_issue
    assert parsed_issue['c'] == 'b'

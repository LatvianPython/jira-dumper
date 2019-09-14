import pytest


@pytest.fixture
def patch_jira(monkeypatch):
    from jira import Issue, Worklog
    import json
    import jira

    class MockJIRA:
        def __init__(self, *args, **kwargs):
            pass

        def _get_json(self, path, params, base):
            with open('./test_data/sample_sla.json', mode='r', encoding='utf-8') as file:
                test_sla = json.loads(file.read())

            return test_sla

        def worklogs(self, issue):
            with open('./test_data/sample_worklog.json', mode='r', encoding='utf-8') as file:
                raw_worklog = json.loads(file.read())
                test_worklog = Worklog(options=None, session=None, raw=raw_worklog)

            return [test_worklog] * 10

        def search_issues(self, *args, **kwargs):
            _ = args, self
            if kwargs['startAt'] > 0:
                return []

            with open('./test_data/sample_issue.json', mode='r', encoding='utf-8') as file:
                raw_issue = json.loads(file.read())
                test_issue = Issue(options=None, session=None, raw=raw_issue)

            return [test_issue]

    monkeypatch.setattr(jira, 'JIRA', MockJIRA)

import pytest


@pytest.fixture
def patch_jira(monkeypatch):
    from jira import Issue
    import json
    import jira

    class MockJIRA:
        def __init__(self, *args, **kwargs):
            pass

        def search_issues(self, *args, **kwargs):
            _ = args, self
            if kwargs['startAt'] > 0:
                return []

            with open('./tests/test_data/sample_issue.json', mode='r', encoding='utf-8') as file:
                raw_issue = json.loads(file.read())
                test_issue = Issue(options=None, session=None, raw=raw_issue)

            return [test_issue]

    monkeypatch.setattr(jira, 'JIRA', MockJIRA)

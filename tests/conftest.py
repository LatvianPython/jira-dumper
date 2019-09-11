import json

import jira
import pytest
from jira import Issue


@pytest.fixture
def patch_jira(monkeypatch):
    class MockJIRA:
        def __init__(self, *args, **kwargs):
            pass

        def search_issues(self, *args, **kwargs):
            if kwargs['startAt'] > 0:
                return []

            import pathlib

            print(pathlib.Path.cwd())

            with open('./tests/sample_issue.json', mode='r', encoding='utf-8') as file:
                raw_issue = json.loads(file.read())
                test_issue = Issue(options=None, session=None, raw=raw_issue)

            return [test_issue]

    monkeypatch.setattr(jira, 'JIRA', MockJIRA)

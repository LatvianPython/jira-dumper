
import base


def test_dumper_basic(patch_jira):

    with base.Dumper(server='https://jira.server.com', jql=None, auth=None) as dumper:
        issues = list(dumper.issues)

        assert len(issues) == 1

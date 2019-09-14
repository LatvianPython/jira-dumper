import pandas as pd

from base import Dumper, IssueField


class CustomDumper(Dumper):
    # can add or override fields, to change this it is best to consult results from the Jira REST API
    assignee = IssueField(['assignee', 'displayName'])  # path from where to take value from REST response
    get_transitions = True # can be just as well turned off, otherwise changelog will be requested from Jira


def main():
    # define which issues to dump via the Jira Query Language (JQL)
    jql = '''project = "Jira Service Desk Cloud" and resolution = unresolved and updatedDate > startOfDay()'''

    # if server is behind authentication, pass optional auth keyword argument -> auth=('username', 'password')
    with CustomDumper(server='https://jira.atlassian.com', jql=jql) as jira_dump:
        pd.DataFrame(jira_dump.issues).to_csv('./issues.csv')
        pd.DataFrame(jira_dump.transitions).to_csv('./transitions.csv')
        pd.DataFrame(jira_dump.worklogs).to_csv('./worklogs.csv')
        pd.DataFrame(jira_dump.comments).to_csv('./comments.csv')


if __name__ == '__main__':
    main()

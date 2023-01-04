import re
from typing import List, Optional

from ebrains_drive.repo import Repo
from ebrains_drive.utils import raise_does_not_exist

if False:
    # for forward-reference type-checking:
    from ebrains_drive.client import DriveApiClient

class Repos(object):
    def __init__(self, client: "DriveApiClient") -> None:
        self.client = client

    def create_repo(self, name: str, password: Optional[str]=None) -> Repo:
        data = {'name': name}
        if password:
            data['passwd'] = password
        repo_json = self.client.post('/api2/repos/', data=data).json()
        return self.get_repo(repo_json['repo_id'])

    @raise_does_not_exist('The requested library does not exist')
    def get_repo(self, repo_id: str) -> Repo:
        """Get the repo which has the id `repo_id`.

        Raises :exc:`DoesNotExist` if no such repo exists.
        """
        repo_json = self.client.get('/api2/repos/' + repo_id).json()
        return Repo.from_json(self.client, repo_json)

    def _remove_duplicate_repos(self, repos: List[Repo]) -> List[Repo]:
        unique_repos: List[Repo] = []
        for repo in repos:
            if repo.id not in [r.id for r in unique_repos]:
                unique_repos.append(repo)
            else:
                if repo.owner != "Organization":
                    unique_repos = [repo if r.id == repo.id else r for r in unique_repos]
        return unique_repos

    def list_repos(self) -> List[Repo]:
        repos_json = self.client.get('/api2/repos/').json()
        repos = [Repo.from_json(self.client, j) for j in repos_json]
        return self._remove_duplicate_repos(repos)

    def get_repos_by_filter(self, filter_name, filter_value):
        """Get all repos which have `filter_name` = `filter_value`.
        """
        repos_json = self.client.get('/api2/repos/').json()
        print
        match_repos = []
        for j in repos_json:
            if filter_name in j.keys() and j[filter_name] == filter_value:
                match_repos.append(Repo.from_json(self.client, j))
        return self._remove_duplicate_repos(match_repos)

    def get_repos_by_name(self, repo_name):
        """Get all repos which have the name `repo_name`.
        """
        return self.get_repos_by_filter("name", repo_name)

    def get_repo_by_url(self, repo_url):
        """Get a single repo associated with specified repo_url
        Example inputs:
        1) https://wiki.ebrains.eu/bin/view/Collabs/collab-testing/subpage
        2) wiki.ebrains.eu/bin/view/Collabs/collab-testing
        3) collab-testing
        """

        regex = r"(?:\/Collabs\/)(.*?)(?:\/.*$|$)"

        matches = re.search(regex, repo_url)
        if matches is None:
            collab_name = repo_url
        else:
            collab_name = matches.group(1)

        match_repos = self.get_repos_by_filter("owner", "collab-" + collab_name + "-administrator")
        if not match_repos:
            match_repos = self.get_repos_by_filter("owner", "collab-" + collab_name + "-editor")
        if not match_repos:
            match_repos = self.get_repos_by_filter("owner", "collab-" + collab_name + "-viewer")

        if len(match_repos) == 0:
            raise Exception("Couldn't identify any repo associated with specified URL!")
        elif len(match_repos) > 1:
            raise Exception("Couldn't uniquely identify the repo associated with specified URL!")
        else:
            return match_repos[0]

#coding: utf-8

import os
import pytest

import ebrains_drive
from tests.utils import randstring
from ebrains_drive.client import DriveApiClient


USER = os.environ.get('SEAFILE_TEST_USERNAME', 'test@seafiletest.com')
TOKEN = os.environ.get('SEAFILE_TEST_TOKEN', 'testtest')


@pytest.fixture(scope='session')
def client() -> DriveApiClient:
    return ebrains_drive.client.DriveApiClient(username=USER, token=TOKEN, env="int")


@pytest.yield_fixture(scope='function')
def repo(client):
    repo_name = 'tmp-测试资料库-%s' % randstring()
    repo = client.repos.create_repo(repo_name)
    try:
        yield repo
    finally:
        repo.delete()

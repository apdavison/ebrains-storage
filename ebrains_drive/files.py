import io
import os
import posixpath
import re
from typing import Dict, List, Optional, Union, BinaryIO, Mapping, Sequence
#from typing import TypeAlias  # Python 3.10+
from ebrains_drive.utils import querystr
from requests.models import Response

if False:
    # for forward-reference type-checking:
    from ebrains_drive.repo import Repo

EntryAsJSON = Dict[str, Union[str, int, None]]


# Note: only files and dirs with contents is assigned an ID; else their ID is set to all zeros
ZERO_OBJ_ID = '0000000000000000000000000000000000000000'

class _SeafDirentBase(object):
    """Base class for :class:`SeafFile` and :class:`SeafDir`.

    It provides implementation of their common operations.
    """
    isdir: Optional[bool] = None

    def __init__(self, repo: "Repo", path: str, object_id: str, obj_type: str, size: int=0) -> None:
        """
        :param:`path` the full path of this entry within its repo, like
        "/documents/example.md"

        :param:`size` The size of a file. It should be zero for a dir.
        """
        self.client = repo.client
        self.repo = repo
        self.path = path
        self.id = object_id
        self.type = obj_type
        self.size = size

    @property
    def name(self) -> str:
        return posixpath.basename(self.path)

    def list_revisions(self):
        pass

    def delete(self) -> Response:
        suffix = 'dir' if self.isdir else 'file'
        url = '/api2/repos/%s/%s/' % (self.repo.id, suffix) + querystr(p=self.path)
        resp = self.client.delete(url)
        return resp

    def rename(self, newname: str) -> bool:
        """Change file/folder name to newname
        """
        suffix = 'dir' if self.isdir else 'file'
        url = '/api2/repos/%s/%s/' % (self.repo.id, suffix) + querystr(p=self.path, reloaddir='true')
        postdata = {'operation': 'rename', 'newname': newname}
        resp = self.client.post(url, data=postdata)
        succeeded = resp.status_code == 200
        if succeeded:
            if self.isdir:
                new_dirent = self.repo.get_dir(os.path.join(os.path.dirname(self.path), newname))
            else:
                new_dirent = self.repo.get_file(os.path.join(os.path.dirname(self.path), newname))
            for key in list(self.__dict__.keys()):
                self.__dict__[key] = new_dirent.__dict__[key]
        return succeeded

    def _copy_move_task(self, operation: str, dirent_type: str, dst_dir: str, dst_repo_id: Optional[str]=None) -> Response:
        url = '/api/v2.1/copy-move-task/'
        src_repo_id = self.repo.id
        src_parent_dir = os.path.dirname(self.path)
        src_dirent_name = os.path.basename(self.path)
        dst_repo_id = dst_repo_id
        dst_parent_dir = dst_dir
        operation = operation
        dirent_type =  dirent_type
        postdata = {'src_repo_id': src_repo_id, 'src_parent_dir': src_parent_dir,
                    'src_dirent_name': src_dirent_name, 'dst_repo_id': dst_repo_id,
                    'dst_parent_dir': dst_parent_dir, 'operation': operation,
                    'dirent_type': dirent_type}
        return self.client.post(url, data=postdata)

    def copyTo(self, dst_dir: str, dst_repo_id: Optional[str]=None) -> bool:
        """Copy file/folder to other directory (also to a different repo)
        """
        if dst_repo_id is None:
            dst_repo_id = self.repo.id

        dirent_type = 'dir' if self.isdir else 'file'
        resp = self._copy_move_task('copy', dirent_type, dst_dir, dst_repo_id)
        return resp.status_code == 200

    def moveTo(self, dst_dir: str, dst_repo_id: Optional[str]=None) -> bool:
        """Move file/folder to other directory (also to a different repo)
        """
        if dst_repo_id is None:
            dst_repo_id = self.repo.id

        dirent_type = 'dir' if self.isdir else 'file'
        resp = self._copy_move_task('move', dirent_type, dst_dir, dst_repo_id)
        succeeded = resp.status_code == 200
        if succeeded:
            new_repo = self.client.repos.get_repo(dst_repo_id)
            dst_path = os.path.join(dst_dir, os.path.basename(self.path))
            if self.isdir:
                new_dirent = new_repo.get_dir(dst_path)
            else:
                new_dirent = new_repo.get_file(dst_path)
            for key in list(self.__dict__.keys()):
                self.__dict__[key] = new_dirent.__dict__[key]
        return succeeded

    def get_share_link(self):
        pass


class SeafDir(_SeafDirentBase):
    isdir = True

    def __init__(self, *args, **kwargs) -> None:
        super(SeafDir, self).__init__(*args, **kwargs)
        self.entries: Optional[List[Union["SeafFile", "SeafDir"]]] = None
        self.entries = kwargs.pop('entries', None)

    def ls(self, entity_type: Optional[str]=None, force_refresh: bool=True) -> List[Union["SeafFile", "SeafDir"]]:
        """List the entries in this dir.

        Return a list of objects of class :class:`SeafFile` or :class:`SeafDir`.
        """
        if entity_type and entity_type not in ["file", "dir"]:
            raise ValueError("Invalid value for parameter `entity_type`; must be 'file' or 'dir'!")
        if self.entries is None or force_refresh:
            self.load_entries()
        assert self.entries is not None  # for the type-checker

        if entity_type:
            return [x for x in self.entries if x.type == entity_type]
        else:
            return self.entries

    def share_to_user(self, email, permission):
        url = '/api2/repos/%s/dir/shared_items/' % self.repo.id + querystr(p=self.path)
        putdata = {
            'share_type': 'user',
            'username': email,
            'permission': permission
        }
        resp = self.client.put(url, data=putdata)
        return resp.status_code == 200

    def create_empty_file(self, name: str) -> "SeafFile":
        """Create a new empty file in this dir.
        Return a :class:`SeafFile` object of the newly created file.
        """
        # TODO: file name validation
        path = posixpath.join(self.path, name)
        url = '/api2/repos/%s/file/' % self.repo.id + querystr(p=path, reloaddir='true')
        postdata = {'operation': 'create'}
        resp = self.client.post(url, data=postdata)
        self.id = resp.headers['oid']
        self.load_entries(resp.json())
        return SeafFile(self.repo, path, ZERO_OBJ_ID, "file", 0)

    def check_exists(self, name: str, entity_type: None=None) -> Union["SeafDir", "SeafFile", bool]:
        """Check if an entity with specified name exists in current directory
        Note: seafile doesn't allow even a sub-directory and file,
              within the same directory, to have the same name
        """
        entity_list = self.ls(entity_type=entity_type, force_refresh=True)
        for e in entity_list:
            if e.name == name:
                return e
        return False

    def mkdir(self, name: str) -> "SeafDir":
        """Create a new sub folder right under this dir.

        Return a :class:`SeafDir` object of the newly created sub folder.
        """
        # check if entity with same name already exists
        if self.check_exists(name):
            raise FileExistsError("File/directory with name = `{}` already exists in current directory!".format(name))

        path = posixpath.join(self.path, name)
        url = '/api2/repos/%s/dir/' % self.repo.id + querystr(p=path, reloaddir='true')
        postdata = {'operation': 'mkdir'}
        resp = self.client.post(url, data=postdata)
        self.id = resp.headers['oid']
        self.load_entries(resp.json())

        # fetch and return created directory object
        return SeafDir(self.repo, path, ZERO_OBJ_ID, "dir")

    def upload(self, fileobj: Union[bytes, BinaryIO], filename: str) -> "SeafFile":
        """Upload a file to this folder.

        :param:fileobj :class:`File` like object
        :param:filename The name of the file

        Return a :class:`SeafFile` object of the newly uploaded file.
        """
        if isinstance(fileobj, bytes):
            fileobj = io.BytesIO(fileobj)
        upload_url = self._get_upload_link()
        files = {
            'file': (filename, fileobj),
            'parent_dir': self.path,
        }
        self.client.post(upload_url, files=files)
        return self.repo.get_file(posixpath.join(self.path, filename))

    def upload_local_file(self, filepath, name=None, overwrite=False):
        """Upload a file to this folder.

        :param:filepath The path to the local file
        :param:name The name of this new file. If None, the name of the local file would be used.

        Return a :class:`SeafFile` object of the newly uploaded file.
        """
        name = name or os.path.basename(filepath)

        # check if entity with same name already exists
        entity_obj = self.check_exists(name)
        if entity_obj:
            if overwrite:
                a = entity_obj.delete()
            else:
                raise FileExistsError("File/directory with name = `{}` already exists in current directory!".format(name))

        with open(filepath, 'rb') as fp:
            return self.upload(fp, name)

    def _get_upload_link(self) -> str:
        url = '/api2/repos/%s/upload-link/' % self.repo.id
        resp = self.client.get(url)
        match = re.match(r'"(.*)"', resp.text)
        assert match is not None  # for type checker
        return match.group(1)

    def get_uploadable_sharelink(self):
        """Generate a uploadable shared link to this dir.

        Return the url of this link.
        """
        pass

    def load_entries(self, dirents_json: Optional[List[EntryAsJSON]]=None) -> None:
        if dirents_json is None:
            url = '/api2/repos/%s/dir/' % self.repo.id + querystr(p=self.path)
            dirents_json = self.client.get(url).json()

        self.entries = [self._load_dirent(entry_json) for entry_json in dirents_json]

    def _load_dirent(self, dirent_json: EntryAsJSON) -> Union["SeafFile", "SeafDir"]:
        assert isinstance(dirent_json['name'], str)  # for the type checker
        assert isinstance(dirent_json['id'], str)
        assert isinstance(dirent_json['type'], str)
        path = posixpath.join(self.path, dirent_json['name'])
        if dirent_json['type'] == 'file':
            assert isinstance(dirent_json['size'], int)
            return SeafFile(self.repo, path, dirent_json['id'], dirent_json['type'], dirent_json['size'])
        else:
            return SeafDir(self.repo, path, dirent_json['id'], dirent_json['type'], 0)

    @property
    def num_entries(self):
        if self.entries is None:
            self.load_entries()
        return len(self.entries) if self.entries is not None else 0

    def __str__(self):
        return 'SeafDir[repo=%s, path=%s, entries=%s]' % \
            (self.repo.id[:6], self.path, self.num_entries)

    __repr__ = __str__


class SeafFile(_SeafDirentBase):
    isdir = False

    def update(self, fileobj):
        """Update the content of this file"""
        pass

    def __str__(self):
        return 'SeafFile[repo=%s, path=%s, size=%s]' % \
            (self.repo.id[:6], self.path, self.size)

    __repr__ = __str__

    def _get_download_link(self) -> str:
        url = '/api2/repos/%s/file/' % self.repo.id + querystr(p=self.path)
        resp = self.client.get(url)
        match = re.match(r'"(.*)"', resp.text)
        assert match is not None  # for the type checker
        return match.group(1)

    def get_content(self) -> bytes:
        """Get the content of the file"""
        url = self._get_download_link()
        return self.client.get(url).content
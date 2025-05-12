"""
storage_utils module is used for all the storage functions.
"""
from abc import ABC, abstractmethod
import os
import subprocess
import requests
from azure.storage.filedatalake import DataLakeServiceClient
from azure.identity import ClientSecretCredential
from .message import Message
from .config import Config
from pathlib import Path

def get_storage_obj(storage_type):
    """
    get_storage_obj method is used to get the storage object.
    StorageUtils.storage_objs is a dict which has singletone for each storage type.
    :param storage_type: storage type for which the connection object it need to create.
    :return : storage object
    """
    if storage_type == Message.adls_gen_2:
        account_name = Config.adls_gen2_account_name()
        container_name = Config.adls_gen2_container_name()
        if (
            StorageUtils.storage_objs.get(
                Message.adls_gen_2 + account_name + container_name, None
            )
            is None
        ):
            StorageUtils.storage_objs[
                Message.adls_gen_2 + account_name + container_name
            ] = AdlsUtilsGen2(
                tenant_id=Config.adls_gen2_tenant_id(),
                client_id=Config.adls_gen2_client_id(),
                client_secret=Config.adls_gen2_client_secret(),
                account_name=Config.adls_gen2_account_name(),
                adls_container=Config.adls_gen2_container_name(),
            )
        return (
            True,
            StorageUtils.storage_objs[
                Message.adls_gen_2 + account_name + container_name
            ],
        )
    if storage_type == Message.hdfs:
        if StorageUtils.storage_objs.get(Message.hdfs, None) is None:
            StorageUtils.storage_objs[Message.hdfs] = Hdfs()
        return True, StorageUtils.storage_objs[Message.hdfs]

    return False, Message.invalid_storage_type


class StorageUtils(ABC):
    """
    StorageUtils is a abstrace class which define the methods need for all the stoarage class.
    All the Storage class has to extend This class.
    """

    storage_objs = dict()

    @abstractmethod
    def check_file(self, file_name):
        """
        check_file method is used to check files is present or not.

        :param file_name: file_name file path need to check
        :return : True if the file is present or False with respective message
        """

    @abstractmethod
    def delete_file(self, file_name):
        """
        delete_file method is used to delete file.

        :param file_name: file_name file path to delete
        :return : True if the file is delted or False with respective message
        """

    @abstractmethod
    def upload_file(self, upload_file_path, local_file_path):
        """
        upload_file method is used to upload file from local_file_path to upload_file_path.

        :param upload_file_path: file path to upload
        :param local_file_path: local file path that need to upload
        :return : True if the file is uploaded or False with respective message
        """

    @abstractmethod
    def download_file(self, download_file_path, local_file_path):
        """
        download method is used to download file from download_file_path to local_file_path.

        :param download_file_path: file path to download
        :param local_file_path: local file path where to download
        :return : True if the file is downloaded or False with respective message
        """


class Hdfs(StorageUtils):
    """
    Hdfs class is used to handel all hdfs operation.
    """

    def upload_file(self, upload_file_path, local_file_path):
        """
        upload_file method is used to upload file from local_file_path to upload_file_path.

        :param upload_file_path: file path to upload
        :param local_file_path: local file path that need to upload
        :return : True if the file is uploaded or False with respective message
        """
        if upload_file_path.split("/")[0] != "":
            if upload_file_path.split("/")[0] != "DMLE":
                upload_file_path = "/DMLE/" + upload_file_path
            else:
                upload_file_path = "/" + upload_file_path
        if upload_file_path.split("/")[1] != "DMLE":
            upload_file_path = "/DMLE" + upload_file_path
        mkdir_cmd = [
            "hdfs",
            "dfs",
            "-mkdir",
            "-p",
            "/".join(upload_file_path.split("/")[0:-1]),
        ]
        self.run_hdfs_cmd(mkdir_cmd)
        upload_cmd = [
            "hdfs",
            "dfs",
            "-copyFromLocal",
            local_file_path,
            upload_file_path,
        ]
        status, _, err = self.run_hdfs_cmd(upload_cmd)
        if status == 0:
            return True, Message.uploaded_successfully
        return False, err.decode()

    def download_file(self, download_file_path, local_file_path):
        """
        download method is used to download file from download_file_path to local_file_path.

        :param download_file_path: file path to download
        :param local_file_path: local file path where to download
        :return : True if the file is downloaded or False with respective message
        """
        if download_file_path.split("/")[0] != "":
            if download_file_path.split("/")[0] != "DMLE":
                download_file_path = "/DMLE/" + download_file_path
            else:
                download_file_path = "/" + download_file_path
        if download_file_path.split("/")[1] != "DMLE":
            download_file_path = "/DMLE" + download_file_path
        folder = "/".join(local_file_path.split("/")[0:-1])
        if not os.path.exists(folder):
            os.makedirs(folder)
        upload_cmd = [
            "hdfs",
            "dfs",
            "-copyToLocal",
            download_file_path,
            local_file_path,
        ]
        status, _, err = self.run_hdfs_cmd(upload_cmd)
        if status == 0:
            return True, Message.downloaded_successfully
        return False, err.decode()

    def check_file(self, file_path):
        """
        check_file method is used to check files is present or not.

        :param file_name: file_name file path need to check
        :return : True if the file is present or False with respective message
        """
        check_file_cmd = [
            "hdfs",
            "dfs",
            "-test",
            "-e",
            file_path,
        ]
        status, _, err = self.run_hdfs_cmd(check_file_cmd)
        if status == 0:
            return True, Message.file_exists
        return False, err.decode()

    def delete_file(self, file_path):
        """
        check_file method is used to check files is present or not.

        :param file_name: file_name file path need to check
        :return : True if the file is present or False with respective message
        """
        return True

    def run_hdfs_cmd(self, args_list):
        """
        run linux commands
        returns : return code stdout, srderr
        """
        try:
            proc = subprocess.Popen(
                args_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            s_output, s_err = proc.communicate()
            s_return = proc.returncode
            return s_return, s_output, s_err
        except Exception as err:
            return 1,"",str(err).encode()

    def get_files_from_directory(self,directory_path):
        '''
        Get list of file paths from the given directory.
        :param directory_path: HDFS folder path to get the all the files inside.
        :return: List of files.
        '''
        get_files_cmd = [
            "hdfs",
            "dfs",
            "-ls",
            directory_path,
        ]
        status, _, err = self.run_hdfs_cmd(get_files_cmd)
        if status == 0:
            return True, Message.file_exists
        return False, err.decode()


class AdlsUtilsGen2(StorageUtils):
    """Class used for all adls operations."""

    def __init__(
        self, tenant_id, client_id, client_secret, account_name, adls_container
    ):
        """Intializer for adls util."""

        credential = ClientSecretCredential(tenant_id, client_id, client_secret)

        self.service_client = DataLakeServiceClient(
            account_url="{}://{}.dfs.core.windows.net".format("https", account_name),
            credential=credential,
        )
        self.file_system_clients = self.service_client.get_file_system_client(
            adls_container
        )

    def check_file(self, file_path):
        """
        check_file method is used to check files is present or not.

        :param file_name: file_name file path need to check
        :return : True if the file is present or False with respective message
        """
        if self.file_system_clients.get_file_client(file_path).exists():
            return True, Message.file_exists
        return False, Message.file_not_exists

    def delete_file(self, file_path):
        """
        delete_file method is used to delete file.

        :param file_name: file_name file path to delete
        :return : True if the file is delted or False with respective message
        """
        self.file_system_clients.delete_file(file_path)
        return not self.file_system_clients.get_file_client(file_path).exists()

    def upload_file(self, upload_file_path, local_file_path):
        """
        Function is used to upload file from local machine to ADLS GEN2.
        :param upload_file_path: FIle path to be uploaded in the ADLS, Ex: sample/test/path/file.csv
        :param local_file_path: File path that has to upload from the local, Ex : home/files/localfile.csv
        :return: True/False
        """
        upload_file_name = upload_file_path.split("/")[-1]
        upload_directory = "/".join(upload_file_path.split("/")[0:-1])
        file_content = open(local_file_path, "rb").read()
        directory_client = self.file_system_clients.get_directory_client(
            upload_directory
        )
        file_client = directory_client.get_file_client(upload_file_name)
        file_client.upload_data(file_content, overwrite=True)
        return True, Message.uploaded_successfully

    def download_file(self, download_file_path, local_file_path):
        """
        Function is used to download file from ADLS GEN2 to local.
        :param download_file_path: Downloadable file path from ADLS. Ex: sample/test/path/file.csv
        :param local_file_path: Download file path into local machine.Ex : home/files/localfile.csv
        :return:
        """
        download_file_name = download_file_path.split("/")[-1]
        download_directory = "/".join(download_file_path.split("/")[0:-1])
        directory_client = self.file_system_clients.get_directory_client(
            download_directory
        )
        file_client = directory_client.get_file_client(download_file_name)
        file_conetnt = file_client.download_file().chunks()
        folder = Path(local_file_path).parent
        if not os.path.exists(folder):
            os.makedirs(folder)
        with open(local_file_path, "wb") as local_file:
            for data in file_conetnt:
                local_file.write(data)
        return True, Message.downloaded_successfully

    def get_file_url(self, file_path):
        """
        Returns the URL where the file is located in the ADLS Gen2
        :param file_path Relative path of the file
        :return: URL of the file
        """
        file_name = Path(file_path).name
        dir_name = Path(file_path).parent.as_posix()
        dir_client = self.file_system_clients.get_directory_client(dir_name)
        file_client = dir_client.get_file_client(file_name)
        return file_client.url

    def get_files_from_directory(self,directory_path):
        '''
        Get list of file paths from the given directory.
        :param directory_path: ADLS folder path to get the all the files inside.
        :return: List of files.
        '''
        file_system_client = self.file_system_clients
        paths = file_system_client.get_paths(path=directory_path,recursive=False)
        return [each_file.name for each_file in paths]


class HttpsDownloader(ABC):
    """Class used for https download."""

    @staticmethod
    def download_file( download_file_path, local_file_path):
        response = requests.get(download_file_path, stream=True)
        if response.status_code == 200:
            total_length = response.headers.get('content-length')
            with open(local_file_path, "wb") as f:
                if total_length is None: # no content length header
                    f.write(response.content)
                else:
                    total_length = int(total_length)
                    written_data = 0
                    for data in response.iter_content(chunk_size=4096):
                        written_data += len(data)
                        f.write(data)
                    #LoggerUtils.get_logger().info("Downloaded {} bytes expected {} bytes".format(written_data,total_length))
                    return True, Message.downloaded_successfully

        else:
            return False, f"{Message.file_not_exists}. Reason: {response.reason}"
    @staticmethod
    def check_file( file_path):
        """
        check_file method is used to check wether file is present or not.

        :param file_name: file_name file path need to check
        :return : True if the file is present or False with respective message
        """
        response = requests.head(file_path)
        if response.status_code == 200:
            return True, Message.file_exists
        return False, Message.file_not_exists

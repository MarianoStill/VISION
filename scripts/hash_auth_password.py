from getpass import getpass

from vision.auth import hash_password


if __name__ == "__main__":
    print(hash_password(getpass("Temporary DEV password (14+ characters): ")))

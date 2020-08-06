import os
import errno


def create_dir(dir_name: str):
    os.makedirs(dir_name, exist_ok=True)


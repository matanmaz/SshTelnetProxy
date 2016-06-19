import os

import mockssh


def server():
    users = {
        "user": r"C:\Users\Lenov\SshTelnetProxy\ssh-keys\id_rsa",
    }
    mockssh.Server(users)

server()
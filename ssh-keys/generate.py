from Crypto.PublicKey import RSA
import os

script_dir = os.getcwd() #<-- absolute dir the script is in
rel_path = "ssh-keys\\ssh_host_rsa_key"
abs_file_path = os.path.join(script_dir, rel_path)
key = RSA.generate(2048)
with open(abs_file_path, 'w+') as content_file:
    content_file.write(key.exportKey('PEM'))
pubkey = key.publickey()

rel_path = "ssh-keys\\ssh_host_rsa_key.pub"
abs_file_path = os.path.join(script_dir, rel_path)
with open(abs_file_path, 'w+') as content_file:
    content_file.write(pubkey.exportKey('OpenSSH'))
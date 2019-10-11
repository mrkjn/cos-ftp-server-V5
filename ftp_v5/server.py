#!/usr/bin/env python
# -*- coding:utf-8 -*-

import logging

from pyftpdlib.servers import FTPServer

from ftp_v5.conf.ftp_config import CosFtpConfig
from ftp_v5.cos_authorizer import CosAuthorizer
from ftp_v5.cos_file_system import CosFileSystem
from ftp_v5.cos_ftp_handler import CosFtpHandler

logging.basicConfig(
    level=CosFtpConfig().log_level,
    format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
    datefmt='%a, %d %b %Y %H:%M:%S',
    filename=CosFtpConfig().log_filename,
    filemode='w'
)


def run(port=2121, passive_ports=range(60000, 65535), masquerade_address=None):
    authorizer = CosAuthorizer()
    for login_user, login_password, home_dir, permission in CosFtpConfig().login_users:
        perm = ""
        if "R" in permission:
            perm = perm + authorizer.read_perms
        if "W" in permission:
            perm = perm + authorizer.write_perms
        authorizer.add_user(login_user, login_password, home_dir, perm=perm)

    handler = CosFtpHandler
    handler.authorizer = authorizer
    handler.abstracted_fs = CosFileSystem
    handler.banner = "Welcome to COS FTP Service"
    handler.permit_foreign_addresses = True

    if masquerade_address is not None:
        handler.masquerade_address = masquerade_address

    handler.passive_ports = passive_ports

    server = FTPServer(("0.0.0.0", port), handler)
    server.max_cons = CosFtpConfig().max_connection_num

    print("starting  ftp server...")

    try:
        server.serve_forever()
    finally:
        server.close_all()


def main():
    # 首先校验配置的合理性
    CosFtpConfig.check_config(CosFtpConfig())

    port = CosFtpConfig().listen_port

    external_ip = CosFtpConfig().masquerade_address
    passive_ports = CosFtpConfig().passive_ports

    run(port=port, masquerade_address=external_ip, passive_ports=passive_ports)

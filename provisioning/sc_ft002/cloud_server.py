# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning._core import Run
from provisioning._pubkey import AddPubKey
from provisioning._pubkey import RepoPubKey
from provisioning._users import AddUser
from provisioning._users import AddUserToGroup
from provisioning.fleet import sc_ft002_cloud


def main():
    sc_ft002_cloud.run([
        # CUT: Personal accounts configuration

        # Java
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get remove -y openjdk-8-* java-*'),
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y openjdk-11-jre'),

        # Install Jenkins.
        Run('curl -fsSL https://pkg.jenkins.io/debian/jenkins.io-2023.key | sudo tee /usr/share/keyrings/jenkins-keyring.asc'),
        Run('echo deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/ | sudo tee /etc/apt/sources.list.d/jenkins.list'),
        Run('sudo apt update'),
        Run('sudo apt install -y jenkins'),
        Run('sudo systemctl enable jenkins'),
        Run('sudo systemctl start jenkins'),

        # Install Docker.
        Run('curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg'),
        Run('sudo chmod a+r /etc/apt/keyrings/docker.gpg'),
        Run('echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu jammy stable" | sudo tee /etc/apt/sources.list.d/docker.list'),
        Run('sudo apt update'),
        Run('sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()

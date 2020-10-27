# Project Gadget

Welcome to Gadget!

Gadget is a utility developed internally at Capco that is used to describe a devops stack of tooling to use in the course of an engagement.
At present, gadget only supports the provisioning of infrastructure in the Azure cloud using terraform and ansible.

## Requirements

The following are required for Gadget to function:

- Python >= 3.6
- VirtualEnv
- Terraform
- Azure CLI configuration (Credentials)

## Access to environment

Access to the environment is only granted by way of OpenVPN tunnel. A compatible OpenVPN client is required.
A recommended client can be downloaded from the OpenVPN website:

- [MacOS](https://docs.openvpn.net/connecting/connecting-to-access-server-with-macos/)
- [Windows](https://openvpn.net/index.php/open-source/downloads.html)
- [Linux](https://openvpn.net/index.php/open-source/downloads.html)

## VPN Administration

The VPN solution utilizes an [OpenVPN](http://openvpn.net) solution hosted on the [PFSense](http://pfsense.org) platform.
The url for the administration console for the VPN is: [https://vpn.canvas.capco-digital.io:9443](https://vpn.canvas.capco-digital.io:9443)

## Installation

### Python Setup

> A virtualenv should be created prior to installation as Gadget will also install a version of ansible and the Azure SDK that may interfere with a local installation.

Create a virtualenv using the python3 installed from the requirements:

```bash
$ virtualenv -p python3 .venv
```

This will insall a python3 based virtualenv in the current directory under the folder `.venv`

Source the virtualenv

```bash
$ source .venv/bin/activate
```

Validate the python virtualenv in the current shell

```bash
$ python -V
Python 3.6.5

$ which python
/Users/mpmn/workspace/.venv/bin/python
```

### Azure configuration

In order for the Azure functionality to work, Gadget will look for the azure credentials file on your system.
The credentials file is located at `~/.azure/credentials`.

Within it should be the profiles representing the accounts you will need setup and defined in the manifest.
An example file would be:

```Ini
[default]
subscription_id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
client_id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
secret=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
tenant=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

[demo]
subscription_id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
tenant=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
client_id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
secret=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

The manifest will configure gadget to use the profile defined in the credentials file to setup the authentication for Azure.

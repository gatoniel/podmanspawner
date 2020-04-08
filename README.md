# podmanspawner

## Overview

Spawner to use podman with JupyterHub

See also this [issue](https://github.com/jupyterhub/dockerspawner/issues/360) on
dockerspawner.

**This Spawner is still in development and might not work properly.** Please
feel free to file issues, when you encounter problems. Version 0.2 seems to work
in my case...

### Technical

Right now we use subprocess.Popen to make the calls to Podman. We should use [podman RestAPI](https://github.com/containers/podman-py).

## Installation

Via pip:

    pip install git+https://github.com/gatoniel/podmanspawner

### Recommendations

Podman itself relies on a correct user environment, especially `$XDG_RUNTIME_DIR`
and `$PATH`. It also relies on the existence of the directory /run/user/UID. It
has read and write permissions only for the current user. You can leverage PAM
with pam_open_session to create this directory with the correct permissions for
the user. This is recommended, when your users cannot login to the machine
separately, e.g. via ssh. PAMs pam_open_session does not work properly in
JupyterHub (see [#2973](https://github.com/jupyterhub/jupyterhub/issues/2973)).
You can find an improved version of JupyterHub
[here](https://github.com/gatoniel/jupyterhub). When using WrapSpawner, you need
to use an [improved version](https://github.com/gatoniel/wrapspawner/), too.
On strict SELinux machines, you might encounter SELinux problems. When using the
PAM stack to open user sessions. I wrote a
[SELinux policy](https://github.com/gatoniel/jupyterhubd_SELinux) that should
work with the above mentioned repos.

Using pam_open_session also adds more security to your JupyterHub, since the
loginuid of the singleuser notebooks is changed to the users ID, making auditing
mor reliable.

## Configuration

If you want to run the PodmanSpawner within the [wrapspawner.ProfilesSpawner](https://github.com/jupyterhub/wrapspawner) use
this in your jupyterhub_config.py. We relax the `c.Spawner.start_timeout` to give Podman some time to pull the image.

```python
c.Spawner.start_timeout = 120
c.JupyterHub.spawner_class = 'wrapspawner.ProfilesSpawner'
c.ProfilesSpawner.profiles = [
        ('Host process / basic python', 'local', 'jupyterhub.spawner.LocalProcessSpawner', {}),
        ('Podman Python 3', 'podman-std', 'podmanspawner.PodmanSpawner', dict(
                podman_additional_cmds=["-v", "/mnt/datahdd:/home/jovyan/datahdd"],
                https_proxy="http://www-proxy1.hrz.uni-marburg.de:3128",
                enable_lab=True,
                )),
        ('Podman Stardist', 'podman-stardist', 'podmanspawner.PodmanSpawner', dict(
                podman_additional_cmds=[
                        "-v", "/mnt/datahdd:/extdata",
                        "--hooks-dir", "/usr/share/containers/oci/hooks.d/",
                        "-e", "NVIDIA_VISIBLE_DEVICES=all"
                        ],
                jupyter_additional_cmds=["--allow-root"],
                enable_lab=True,
                image="dir:/mnt/datahdd/share/podman_images/stardist",
                start_cmd="jupyterhub-singleuser",
                conthome="/home/USERNAME/",
                startatconthome=True,
                )),
        ]
```

I might be userful to use the `podman push` command to [push](https://github.com/containers/libpod/blob/master/docs/source/markdown/podman-push.1.md) the images you use to a local directory. This might speed up start time of the spawner, since the image must not be downloaded, also you dont need to push specially created images to an online repo...

## Known issues

Most of Jupyters containers change the user to jovyan. Due to the user namespace
mapping of Podman this user has no access rights on the host system. This means
that users cannot access their mounted homefolders properly. I see two solutions
to overcome this situation:
1. Change the jupyter images, so that they use the root user of the container.
   The root user in the container is mapped to the actual running user on the
   host by podman.
2. Grant permissions on the host for the jovyan user of each user. This adds a
   separate routine that has to be called for every user...

## ToDos:

* How to use the [podman RestAPI](https://github.com/containers/podman-py). See this [issue](https://github.com/containers/python-podman/issues/16#issuecomment-605439792)?
* Implement correct move_certs routine. This could be solved when users access
  the notebook as root.

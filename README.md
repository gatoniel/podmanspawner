# podmanspawner

## Overview

Spawner to use podman with JupyterHub

See also this [issue](https://github.com/jupyterhub/dockerspawner/issues/360) on
dockerspawner.

**This Spawner is in development and is not working properly.** This is a
minimal working example.

### Technical

Right now we use subprocess.Popen to make the calls to Podman. We should use [podman RestAPI](https://github.com/containers/podman-py).

## Installation

Via pip:

    pip install git+https://github.com/gatoniel/podmanspawner

## Configuration

If you want to run the PodmanSpawner within the [wrapspawner.ProfilesSpawner](https://github.com/jupyterhub/wrapspawner) use
this in your jupyterhub_config.py. We relax the `c.Spawner.start_timeout` to give Podman some time to pull the image.

```python
c.Spawner.start_timeout = 120
c.JupyterHub.spawner_class = 'wrapspawner.ProfilesSpawner'
c.ProfilesSpawner.profiles = [
    ('Host process / basic python', 'local', 'jupyterhub.spawner.LocalProcessSpawner', {}),
    ('Podman Python 3', 'podman-std', 'podmanspawner.PodmanSpawner', dict(
            # mount an additional volume
            podman_additional_cmds=["-v", "/mnt/datahdd:/home/jovyan/datahdd"],
            # you might need to add a proxy, so Podman is able to use it
            # when pulling the image
            https_proxy="<some-proxy>",
            # check whether JupyterLab should be started
            enable_lab=True,
            # add commands to alter the behaviour of Jupyter
            jupyter_additional_cmds=[],
            )),
    ]
```

## Known issues

You should run this with a user that has a low UID on the host system. UID=1000 and UID=1001
worked out for me on CentOS 8. See this [issue](https://github.com/gatoniel/podmanspawner/issues/2).

## ToDos:

* How to use the [podman RestAPI](https://github.com/containers/podman-py). See this [issue](https://github.com/containers/python-podman/issues/16#issuecomment-605439792)?
* Solve the UID issues. Can we mount /home/USER:/home/USER and bypass the /home/jovyan in the image?
* Implement correct rights to use the mounted folders, see this [issue](https://github.com/gatoniel/podmanspawner/issues/1).
* Implement correct move_certs routine.
